/*
 * bt_core.c: Low-level BlueZ D-Bus operations, RFKill controls, and state persistence
 */

#include "sys_bt.h"
#include <fcntl.h>
#include <sys/types.h>
#include <dirent.h>

static char *get_hci_rfkill_id(void) {
    GDir *dir = g_dir_open("/sys/class/rfkill", 0, NULL);
    if (!dir) return NULL;

    const gchar *entry;
    char *found_id = NULL;

    while ((entry = g_dir_read_name(dir)) != NULL) {
        if (!g_str_has_prefix(entry, "rfkill")) continue;

        char *name_path = g_build_filename("/sys/class/rfkill", entry, "name", NULL);
        char *name_content = NULL;

        if (g_file_get_contents(name_path, &name_content, NULL, NULL)) {
            g_strstrip(name_content);
            if (g_str_has_prefix(name_content, "hci")) {
                found_id = g_strdup(entry + 6); /* "rfkill7" -> "7" */
                g_free(name_content);
                g_free(name_path);
                break;
            }
            g_free(name_content);
        }
        g_free(name_path);
    }
    g_dir_close(dir);
    return found_id;
}

gboolean bt_is_rfkill_blocked(void) {
    GDir *dir = g_dir_open("/sys/class/rfkill", 0, NULL);
    if (!dir) return FALSE;

    const gchar *entry;
    gboolean blocked = FALSE;

    while ((entry = g_dir_read_name(dir)) != NULL) {
        if (!g_str_has_prefix(entry, "rfkill")) continue;

        char *type_path = g_build_filename("/sys/class/rfkill", entry, "type", NULL);
        char *type_content = NULL;

        if (g_file_get_contents(type_path, &type_content, NULL, NULL)) {
            g_strstrip(type_content);
            if (g_strcmp0(type_content, "bluetooth") == 0) {
                char *name_path = g_build_filename("/sys/class/rfkill", entry, "name", NULL);
                char *name_content = NULL;
                gboolean is_hci = FALSE;
                if (g_file_get_contents(name_path, &name_content, NULL, NULL)) {
                    g_strstrip(name_content);
                    if (g_str_has_prefix(name_content, "hci")) is_hci = TRUE;
                    g_free(name_content);
                }
                g_free(name_path);

                char *soft_path = g_build_filename("/sys/class/rfkill", entry, "soft", NULL);
                char *soft_content = NULL;

                if (g_file_get_contents(soft_path, &soft_content, NULL, NULL)) {
                    g_strstrip(soft_content);
                    if (g_strcmp0(soft_content, "1") == 0) {
                        blocked = TRUE;
                    }
                    g_free(soft_content);
                }
                g_free(soft_path);
                if (is_hci && blocked) {
                    g_free(type_content);
                    break;
                }
            }
            g_free(type_content);
        }
        g_free(type_path);
    }
    g_dir_close(dir);
    return blocked;
}

void bt_rfkill_set_blocked(gboolean block) {
    char *hci_id = get_hci_rfkill_id();
    char *cmd = NULL;
    if (hci_id) {
        cmd = g_strdup_printf("rfkill %s %s >/dev/null 2>&1", block ? "block" : "unblock", hci_id);
        g_free(hci_id);
    } else {
        cmd = g_strdup_printf("rfkill %s bluetooth >/dev/null 2>&1", block ? "block" : "unblock");
    }
    int res = system(cmd);
    (void)res;
    g_free(cmd);
}

void bt_notify(const char *summary, const char *body, const char *icon) {
    if (!summary) return;

    /* Use notify-send which links directly to sys-notif */
    GPtrArray *argv = g_ptr_array_new();
    g_ptr_array_add(argv, (gpointer)"notify-send");
    g_ptr_array_add(argv, (gpointer)"-a");
    g_ptr_array_add(argv, (gpointer)"sys-bt");
    if (icon && strlen(icon) > 0) {
        g_ptr_array_add(argv, (gpointer)"-i");
        g_ptr_array_add(argv, (gpointer)icon);
    }
    g_ptr_array_add(argv, (gpointer)summary);
    if (body && strlen(body) > 0) {
        g_ptr_array_add(argv, (gpointer)body);
    }
    g_ptr_array_add(argv, NULL);

    GError *error = NULL;
    g_spawn_async(NULL, (gchar **)argv->pdata, NULL, G_SPAWN_SEARCH_PATH, NULL, NULL, NULL, &error);
    if (error) {
        g_error_free(error);
    }
    g_ptr_array_free(argv, TRUE);
}

BtSystemState *bt_system_state_new(void) {
    BtSystemState *state = g_new0(BtSystemState, 1);
    state->timeout_seconds = SYS_BT_DEFAULT_TIMEOUT;
    return state;
}

static void free_device(gpointer data) {
    BtDevice *dev = (BtDevice *)data;
    if (!dev) return;
    g_free(dev->path);
    g_free(dev->address);
    g_free(dev->name);
    g_free(dev->alias);
    g_free(dev->icon);
    g_free(dev);
}

void bt_system_state_free(BtSystemState *state) {
    if (!state) return;
    g_free(state->adapter.path);
    g_free(state->adapter.name);
    g_free(state->adapter.alias);
    g_free(state->adapter.address);

    if (state->devices) {
        g_list_free_full(state->devices, free_device);
        state->devices = NULL;
    }
    g_free(state);
}

gboolean bt_query_system_state(GDBusConnection *conn, BtSystemState *state) {
    if (!state) return FALSE;

    state->rfkill_blocked = bt_is_rfkill_blocked();

    if (!conn) return FALSE;

    GError *error = NULL;
    GVariant *result = g_dbus_connection_call_sync(
        conn,
        BLUEZ_BUS_NAME,
        BLUEZ_OBJ_PATH,
        BLUEZ_IFACE_OBJ_MANAGER,
        "GetManagedObjects",
        NULL,
        G_VARIANT_TYPE("(a{oa{sa{sv}}})"),
        G_DBUS_CALL_FLAGS_NONE,
        2000,
        NULL,
        &error
    );

    if (!result) {
        if (error) g_error_free(error);
        return FALSE;
    }

    /* Clear any previously stored adapter & devices */
    g_free(state->adapter.path);
    g_free(state->adapter.name);
    g_free(state->adapter.alias);
    g_free(state->adapter.address);
    memset(&state->adapter, 0, sizeof(BtAdapter));
    state->has_adapter = FALSE;

    if (state->devices) {
        g_list_free_full(state->devices, free_device);
        state->devices = NULL;
    }
    state->connected_count = 0;

    GVariant *objects_dict = g_variant_get_child_value(result, 0);
    GVariantIter objects_iter;
    g_variant_iter_init(&objects_iter, objects_dict);

    const gchar *obj_path;
    GVariant *ifaces_dict;

    while (g_variant_iter_next(&objects_iter, "{&o@a{sa{sv}}}", &obj_path, &ifaces_dict)) {
        GVariantIter ifaces_iter;
        g_variant_iter_init(&ifaces_iter, ifaces_dict);

        const gchar *iface_name;
        GVariant *props_dict;

        while (g_variant_iter_next(&ifaces_iter, "{&s@a{sv}}", &iface_name, &props_dict)) {
            if (g_strcmp0(iface_name, BLUEZ_IFACE_ADAPTER) == 0 && !state->has_adapter) {
                state->has_adapter = TRUE;
                state->adapter.path = g_strdup(obj_path);

                GVariantIter props_iter;
                g_variant_iter_init(&props_iter, props_dict);
                const gchar *key;
                GVariant *val;

                while (g_variant_iter_next(&props_iter, "{&sv}", &key, &val)) {
                    if (g_strcmp0(key, "Powered") == 0) {
                        state->adapter.powered = g_variant_get_boolean(val);
                    } else if (g_strcmp0(key, "Discovering") == 0) {
                        state->adapter.discovering = g_variant_get_boolean(val);
                    } else if (g_strcmp0(key, "Name") == 0) {
                        state->adapter.name = g_strdup(g_variant_get_string(val, NULL));
                    } else if (g_strcmp0(key, "Alias") == 0) {
                        state->adapter.alias = g_strdup(g_variant_get_string(val, NULL));
                    } else if (g_strcmp0(key, "Address") == 0) {
                        state->adapter.address = g_strdup(g_variant_get_string(val, NULL));
                    }
                    g_variant_unref(val);
                }
            } else if (g_strcmp0(iface_name, BLUEZ_IFACE_DEVICE) == 0) {
                BtDevice *dev = g_new0(BtDevice, 1);
                dev->path = g_strdup(obj_path);

                GVariantIter props_iter;
                g_variant_iter_init(&props_iter, props_dict);
                const gchar *key;
                GVariant *val;

                while (g_variant_iter_next(&props_iter, "{&sv}", &key, &val)) {
                    if (g_strcmp0(key, "Address") == 0) {
                        dev->address = g_strdup(g_variant_get_string(val, NULL));
                    } else if (g_strcmp0(key, "Name") == 0) {
                        dev->name = g_strdup(g_variant_get_string(val, NULL));
                    } else if (g_strcmp0(key, "Alias") == 0) {
                        dev->alias = g_strdup(g_variant_get_string(val, NULL));
                    } else if (g_strcmp0(key, "Icon") == 0) {
                        dev->icon = g_strdup(g_variant_get_string(val, NULL));
                    } else if (g_strcmp0(key, "Paired") == 0) {
                        dev->paired = g_variant_get_boolean(val);
                    } else if (g_strcmp0(key, "Connected") == 0) {
                        dev->connected = g_variant_get_boolean(val);
                    } else if (g_strcmp0(key, "Trusted") == 0) {
                        dev->trusted = g_variant_get_boolean(val);
                    }
                    g_variant_unref(val);
                }

                if (dev->connected) {
                    state->connected_count++;
                }

                state->devices = g_list_append(state->devices, dev);
            }
            g_variant_unref(props_dict);
        }
        g_variant_unref(ifaces_dict);
    }

    g_variant_unref(objects_dict);
    g_variant_unref(result);

    /* Merge daemon status if state file exists */
    bt_read_state_file(state);

    return TRUE;
}

gboolean bt_adapter_set_powered(GDBusConnection *conn, const char *adapter_path, gboolean powered) {
    if (!conn || !adapter_path) return FALSE;

    int retries = 8;
    while (retries-- > 0) {
        GError *error = NULL;
        GVariant *result = g_dbus_connection_call_sync(
            conn,
            BLUEZ_BUS_NAME,
            adapter_path,
            BLUEZ_IFACE_PROPERTIES,
            "Set",
            g_variant_new("(ssv)", BLUEZ_IFACE_ADAPTER, "Powered", g_variant_new_boolean(powered)),
            NULL,
            G_DBUS_CALL_FLAGS_NONE,
            3000,
            NULL,
            &error
        );

        if (result) {
            g_variant_unref(result);
            return TRUE;
        }

        if (error) {
            if (strstr(error->message, "Error.Busy") && retries > 0) {
                g_error_free(error);
                g_usleep(250000); /* 250ms backoff while hardware initializes */
                continue;
            }
            g_printerr("Failed to set Powered=%d on %s: %s\n", powered, adapter_path, error->message);
            g_error_free(error);
        }
        break;
    }

    return FALSE;
}

gboolean bt_adapter_start_discovery(GDBusConnection *conn, const char *adapter_path) {
    if (!conn || !adapter_path) return FALSE;

    GError *error = NULL;
    GVariant *result = g_dbus_connection_call_sync(
        conn,
        BLUEZ_BUS_NAME,
        adapter_path,
        BLUEZ_IFACE_ADAPTER,
        "StartDiscovery",
        NULL,
        NULL,
        G_DBUS_CALL_FLAGS_NONE,
        3000,
        NULL,
        &error
    );

    if (!result) {
        if (error) g_error_free(error);
        return FALSE;
    }
    g_variant_unref(result);
    return TRUE;
}

gboolean bt_adapter_stop_discovery(GDBusConnection *conn, const char *adapter_path) {
    if (!conn || !adapter_path) return FALSE;

    GError *error = NULL;
    GVariant *result = g_dbus_connection_call_sync(
        conn,
        BLUEZ_BUS_NAME,
        adapter_path,
        BLUEZ_IFACE_ADAPTER,
        "StopDiscovery",
        NULL,
        NULL,
        G_DBUS_CALL_FLAGS_NONE,
        3000,
        NULL,
        &error
    );

    if (!result) {
        if (error) g_error_free(error);
        return FALSE;
    }
    g_variant_unref(result);
    return TRUE;
}

gboolean bt_device_connect(GDBusConnection *conn, const char *device_path, char **error_msg) {
    if (!conn || !device_path) return FALSE;

    GError *error = NULL;
    GVariant *result = g_dbus_connection_call_sync(
        conn,
        BLUEZ_BUS_NAME,
        device_path,
        BLUEZ_IFACE_DEVICE,
        "Connect",
        NULL,
        NULL,
        G_DBUS_CALL_FLAGS_NONE,
        15000, /* 15s timeout for connection handshake */
        NULL,
        &error
    );

    if (!result) {
        if (error) {
            if (error_msg) *error_msg = g_strdup(error->message);
            g_error_free(error);
        }
        return FALSE;
    }
    g_variant_unref(result);
    return TRUE;
}

gboolean bt_device_disconnect(GDBusConnection *conn, const char *device_path, char **error_msg) {
    if (!conn || !device_path) return FALSE;

    GError *error = NULL;
    GVariant *result = g_dbus_connection_call_sync(
        conn,
        BLUEZ_BUS_NAME,
        device_path,
        BLUEZ_IFACE_DEVICE,
        "Disconnect",
        NULL,
        NULL,
        G_DBUS_CALL_FLAGS_NONE,
        5000,
        NULL,
        &error
    );

    if (!result) {
        if (error) {
            if (error_msg) *error_msg = g_strdup(error->message);
            g_error_free(error);
        }
        return FALSE;
    }
    g_variant_unref(result);
    return TRUE;
}

char *bt_get_state_file_path(void) {
    const char *runtime_dir = g_get_user_runtime_dir();
    if (!runtime_dir || strlen(runtime_dir) == 0) {
        runtime_dir = "/tmp";
    }
    return g_build_filename(runtime_dir, "sys-bt.json", NULL);
}

void bt_write_state_file(const BtSystemState *state) {
    char *path = bt_get_state_file_path();
    char *tmp_path = g_strdup_printf("%s.tmp.%d", path, (int)getpid());

    FILE *fp = fopen(tmp_path, "w");
    if (!fp) {
        g_free(tmp_path);
        g_free(path);
        return;
    }

    fprintf(fp, "{\n");
    fprintf(fp, "  \"daemon_pid\": %d,\n", (int)getpid());
    fprintf(fp, "  \"powered\": %s,\n", (state->has_adapter && state->adapter.powered) ? "true" : "false");
    fprintf(fp, "  \"rfkill_blocked\": %s,\n", state->rfkill_blocked ? "true" : "false");
    fprintf(fp, "  \"connected_count\": %d,\n", state->connected_count);
    fprintf(fp, "  \"connected_devices\": [");

    int c = 0;
    for (GList *l = state->devices; l != NULL; l = l->next) {
        BtDevice *dev = (BtDevice *)l->data;
        if (dev->connected) {
            fprintf(fp, "%s\"%s\"", c > 0 ? ", " : "", dev->alias ? dev->alias : dev->address);
            c++;
        }
    }
    fprintf(fp, "],\n");
    fprintf(fp, "  \"timer_armed\": %s,\n", state->timer_armed ? "true" : "false");
    fprintf(fp, "  \"timeout_seconds\": %d,\n", state->timeout_seconds);
    fprintf(fp, "  \"deadline_epoch\": %ld\n", (long)state->deadline_epoch);
    fprintf(fp, "}\n");
    fclose(fp);

    /* Atomic rename */
    rename(tmp_path, path);

    g_free(tmp_path);
    g_free(path);
}

gboolean bt_read_state_file(BtSystemState *state) {
    char *path = bt_get_state_file_path();
    char *content = NULL;

    if (!g_file_get_contents(path, &content, NULL, NULL)) {
        g_free(path);
        state->daemon_active = FALSE;
        return FALSE;
    }
    g_free(path);

    /* Simple parsing of key-value pairs */
    int pid = 0;
    long deadline = 0;
    int timeout = 0;

    char *line = strtok(content, "\n");
    while (line) {
        if (strstr(line, "\"daemon_pid\":")) {
            sscanf(line, " \"daemon_pid\": %d,", &pid);
        } else if (strstr(line, "\"timer_armed\": true")) {
            state->timer_armed = TRUE;
        } else if (strstr(line, "\"timer_armed\": false")) {
            state->timer_armed = FALSE;
        } else if (strstr(line, "\"timeout_seconds\":")) {
            sscanf(line, " \"timeout_seconds\": %d,", &timeout);
        } else if (strstr(line, "\"deadline_epoch\":")) {
            sscanf(line, " \"deadline_epoch\": %ld", &deadline);
        }
        line = strtok(NULL, "\n");
    }

    g_free(content);

    state->daemon_pid = (pid_t)pid;
    state->deadline_epoch = deadline;
    if (timeout > 0) state->timeout_seconds = timeout;

    /* Verify if process is running */
    if (pid > 0 && kill(pid, 0) == 0) {
        state->daemon_active = TRUE;
    } else {
        state->daemon_active = FALSE;
        state->timer_armed = FALSE;
    }

    return TRUE;
}

void bt_remove_state_file(void) {
    char *path = bt_get_state_file_path();
    unlink(path);
    g_free(path);
}
