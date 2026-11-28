#include "sys-polkit-listener.h"
#include <malloc.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

G_DEFINE_TYPE(SysPolkitListener, sys_polkit_listener, POLKIT_AGENT_TYPE_LISTENER)

typedef struct _AuthRequest {
    SysPolkitListener   *listener;
    PolkitAgentSession  *session;
    GTask               *task;
    GCancellable        *cancellable;
    gulong               cancellable_id;
    guint                timeout_id;

    gchar               *action_id;
    gchar               *message;
    gchar               *icon_name;
    gchar               *cookie;
    GList               *identities;
    PolkitIdentity      *selected_identity;

    GPid                 worker_pid;
    gint                 worker_in_fd;
    GIOChannel          *worker_out_ch;
    guint                worker_out_watch;
    guint                worker_child_watch;

    gboolean             completed;
    gboolean             in_progress;
    gboolean             awaiting_request;
    gchar               *pending_password;
} AuthRequest;

static void start_session(AuthRequest *req);
static void finish_request(AuthRequest *req);
static gboolean on_auth_timeout(gpointer user_data);

static void clear_pending_password(AuthRequest *req) {
    if (req->pending_password != NULL) {
        explicit_bzero(req->pending_password, strlen(req->pending_password));
        g_free(req->pending_password);
        req->pending_password = NULL;
    }
}

static void arm_auth_timeout(AuthRequest *req, guint seconds) {
    if (req->timeout_id != 0) {
        g_source_remove(req->timeout_id);
        req->timeout_id = 0;
    }
    req->timeout_id = g_timeout_add_seconds(seconds, on_auth_timeout, req);
}

static gchar *encode_b64_or_dash(const gchar *s) {
    if (s == NULL || s[0] == '\0') {
        return g_strdup("-");
    }
    return g_base64_encode((const guchar *)s, strlen(s));
}

static gchar *decode_b64_str(const gchar *b64) {
    if (b64 == NULL || b64[0] == '\0' || g_strcmp0(b64, "-") == 0) {
        return g_strdup("");
    }
    gsize out_len = 0;
    guchar *raw = g_base64_decode(b64, &out_len);
    gchar *res = g_malloc(out_len + 1);
    if (out_len > 0) memcpy(res, raw, out_len);
    res[out_len] = '\0';
    g_free(raw);
    return res;
}

static void worker_send_line(AuthRequest *req, const gchar *line) {
    if (req->worker_in_fd < 0 || line == NULL) return;
    size_t len = strlen(line);
    size_t off = 0;
    while (off < len) {
        ssize_t n = write(req->worker_in_fd, line + off, len - off);
        if (n <= 0) break;
        off += (size_t)n;
    }
}

static void worker_send_text_cmd(AuthRequest *req, const gchar *cmd, const gchar *text) {
    gchar *b64 = encode_b64_or_dash(text);
    gchar *line = g_strdup_printf("%s\t%s\n", cmd, b64);
    worker_send_line(req, line);
    g_free(line);
    g_free(b64);
}

static void worker_send_prompt(AuthRequest *req, const gchar *prompt, gboolean echo_on) {
    gchar *b64 = encode_b64_or_dash(prompt);
    gchar *line = g_strdup_printf("PROMPT\t%d\t%s\n", echo_on ? 1 : 0, b64);
    worker_send_line(req, line);
    g_free(line);
    g_free(b64);
}

static void worker_send_sensitive(AuthRequest *req, gboolean sensitive) {
    gchar *line = g_strdup_printf("SENSITIVE\t%d\n", sensitive ? 1 : 0);
    worker_send_line(req, line);
    g_free(line);
}

static void close_worker(AuthRequest *req) {
    if (req->worker_in_fd >= 0) {
        worker_send_line(req, "QUIT\n");
        close(req->worker_in_fd);
        req->worker_in_fd = -1;
    }
    if (req->worker_out_watch != 0) {
        g_source_remove(req->worker_out_watch);
        req->worker_out_watch = 0;
    }
    if (req->worker_out_ch != NULL) {
        g_io_channel_unref(req->worker_out_ch);
        req->worker_out_ch = NULL;
    }
    if (req->worker_child_watch != 0) {
        g_source_remove(req->worker_child_watch);
        req->worker_child_watch = 0;
    }
    if (req->worker_pid > 0) {
        g_spawn_close_pid(req->worker_pid);
        req->worker_pid = 0;
    }
}

static void disconnect_session(AuthRequest *req) {
    if (req->session != NULL) {
        g_signal_handlers_disconnect_by_data(req->session, req);
        polkit_agent_session_cancel(req->session);
        g_object_unref(req->session);
        req->session = NULL;
    }
    req->awaiting_request = FALSE;
}

static gboolean on_auth_timeout(gpointer user_data) {
    AuthRequest *req = (AuthRequest *)user_data;
    req->timeout_id = 0;

    if (req->completed) return G_SOURCE_REMOVE;

    g_warning("sys-polkit: Authentication timed out with no response from Polkit Authority.");

    disconnect_session(req);
    clear_pending_password(req);
    req->in_progress = FALSE;

    worker_send_text_cmd(req, "INFO", "");
    worker_send_text_cmd(req, "ERROR", "Authentication timed out. Please try again or cancel.");
    worker_send_line(req, "CLEAR\n");
    worker_send_sensitive(req, TRUE);
    worker_send_line(req, "FOCUS\n");

    start_session(req);
    return G_SOURCE_REMOVE;
}

static void handle_dialog_submit(AuthRequest *req, const gchar *password) {
    if (req->completed || req->in_progress) return;

    if (req->session == NULL) {
        g_warning("sys-polkit: Submit attempted but session is NULL.");
        worker_send_text_cmd(req, "ERROR", "Authentication session not available.");
        worker_send_sensitive(req, TRUE);
        return;
    }

    worker_send_text_cmd(req, "ERROR", "");
    worker_send_sensitive(req, FALSE);
    req->in_progress = TRUE;

    if (req->awaiting_request) {
        req->awaiting_request = FALSE;
        worker_send_text_cmd(req, "INFO", "Verifying credentials...");
        arm_auth_timeout(req, 12);
        polkit_agent_session_response(req->session, password);
    } else {
        clear_pending_password(req);
        req->pending_password = g_strdup(password);
        worker_send_text_cmd(req, "INFO", "Password queued — waiting for fingerprint / PAM...");
        arm_auth_timeout(req, 35);
    }
}

static void handle_dialog_cancel(AuthRequest *req) {
    if (req->completed) return;

    g_info("sys-polkit: Dialog cancelled by user.");
    req->completed = TRUE;

    if (req->timeout_id != 0) {
        g_source_remove(req->timeout_id);
        req->timeout_id = 0;
    }

    if (req->session != NULL) {
        polkit_agent_session_cancel(req->session);
    }

    if (req->task != NULL && !g_task_get_completed(req->task)) {
        g_task_return_new_error(req->task, POLKIT_ERROR, POLKIT_ERROR_CANCELLED, "Authentication cancelled by user");
    }
    finish_request(req);
}

static void handle_dialog_identity_changed(AuthRequest *req, int idx) {
    if (req->completed) return;
    PolkitIdentity *identity = POLKIT_IDENTITY(g_list_nth_data(req->identities, (guint)idx));
    if (identity == NULL) return;

    if (req->timeout_id != 0) {
        g_source_remove(req->timeout_id);
        req->timeout_id = 0;
    }
    req->in_progress = FALSE;

    req->selected_identity = identity;
    worker_send_text_cmd(req, "INFO", "");
    worker_send_text_cmd(req, "ERROR", "");
    worker_send_line(req, "CLEAR\n");
    start_session(req);
}

static gboolean on_worker_stdout(GIOChannel *src, GIOCondition cond, gpointer user_data) {
    AuthRequest *req = (AuthRequest *)user_data;

    if (cond & G_IO_IN) {
        gchar *line = NULL;
        gsize len = 0;
        GError *err = NULL;
        GIOStatus st;
        while ((st = g_io_channel_read_line(src, &line, &len, NULL, &err)) == G_IO_STATUS_NORMAL && line != NULL) {
            g_strchomp(line);
            gchar **parts = g_strsplit(line, "\t", 2);
            const gchar *cmd = (parts && parts[0]) ? parts[0] : "";

            if (g_strcmp0(cmd, "SUBMIT") == 0) {
                gchar *pw = decode_b64_str(parts[1] ? parts[1] : "-");
                handle_dialog_submit(req, pw);
                explicit_bzero(pw, strlen(pw));
                g_free(pw);
            } else if (g_strcmp0(cmd, "CANCEL") == 0) {
                g_strfreev(parts);
                explicit_bzero(line, strlen(line));
                g_free(line);
                handle_dialog_cancel(req);
                return G_SOURCE_REMOVE;
            } else if (g_strcmp0(cmd, "IDENTITY") == 0 && parts[1] != NULL) {
                handle_dialog_identity_changed(req, atoi(parts[1]));
            }

            g_strfreev(parts);
            explicit_bzero(line, strlen(line));
            g_free(line);
            line = NULL;
        }
        g_clear_error(&err);
        g_free(line);
    }

    if (cond & (G_IO_HUP | G_IO_ERR)) {
        req->worker_out_watch = 0;
        if (!req->completed) {
            handle_dialog_cancel(req);
        }
        return G_SOURCE_REMOVE;
    }
    return G_SOURCE_CONTINUE;
}

static void on_worker_exit(GPid pid, gint status, gpointer user_data) {
    (void)pid;
    (void)status;
    AuthRequest *req = (AuthRequest *)user_data;
    req->worker_child_watch = 0;
    if (!req->completed) {
        handle_dialog_cancel(req);
    }
}

static gboolean spawn_dialog_worker(AuthRequest *req) {
    gchar *self_exe = g_file_read_link("/proc/self/exe", NULL);
    if (self_exe == NULL) {
        self_exe = g_strdup("sys-polkit");
    }
    gchar *argv[] = { self_exe, "--dialog-worker", NULL };
    gint in_fd = -1, out_fd = -1;
    GError *err = NULL;

    gboolean ok = g_spawn_async_with_pipes(
        NULL, argv, NULL,
        G_SPAWN_DO_NOT_REAP_CHILD | G_SPAWN_SEARCH_PATH,
        NULL, NULL,
        &req->worker_pid, &in_fd, &out_fd, NULL, &err
    );
    g_free(self_exe);

    if (!ok) {
        g_warning("sys-polkit: Failed to spawn dialog worker: %s", err ? err->message : "unknown");
        g_clear_error(&err);
        return FALSE;
    }

    req->worker_in_fd = in_fd;
    req->worker_out_ch = g_io_channel_unix_new(out_fd);
    g_io_channel_set_encoding(req->worker_out_ch, NULL, NULL);
    g_io_channel_set_flags(req->worker_out_ch, G_IO_FLAG_NONBLOCK, NULL);
    g_io_channel_set_close_on_unref(req->worker_out_ch, TRUE);

    req->worker_out_watch = g_io_add_watch(req->worker_out_ch, G_IO_IN | G_IO_HUP | G_IO_ERR, on_worker_stdout, req);
    req->worker_child_watch = g_child_watch_add(req->worker_pid, on_worker_exit, req);

    /* Send INIT payload */
    gchar *b_act = encode_b64_or_dash(req->action_id);
    gchar *b_msg = encode_b64_or_dash(req->message);
    gchar *b_ico = encode_b64_or_dash(req->icon_name);
    guint n_ids = g_list_length(req->identities);

    GString *init_line = g_string_new(NULL);
    g_string_printf(init_line, "INIT\t%s\t%s\t%s\t%u", b_act, b_msg, b_ico, n_ids);
    for (GList *l = req->identities; l != NULL; l = l->next) {
        gchar *id_s = polkit_identity_to_string(POLKIT_IDENTITY(l->data));
        gchar *b_id = encode_b64_or_dash(id_s);
        g_string_append_printf(init_line, "\t%s", b_id);
        g_free(b_id);
        g_free(id_s);
    }
    g_string_append_c(init_line, '\n');

    worker_send_line(req, init_line->str);

    g_string_free(init_line, TRUE);
    g_free(b_act);
    g_free(b_msg);
    g_free(b_ico);
    return TRUE;
}

static gboolean do_cancellable_cancel(gpointer user_data) {
    AuthRequest *req = (AuthRequest *)user_data;
    if (req->completed) return G_SOURCE_REMOVE;

    g_info("sys-polkit: External D-Bus cancellation executed, destroying dialog.");
    req->completed = TRUE;

    if (req->timeout_id != 0) {
        g_source_remove(req->timeout_id);
        req->timeout_id = 0;
    }

    if (req->session != NULL) {
        polkit_agent_session_cancel(req->session);
    }

    if (req->task != NULL && !g_task_get_completed(req->task)) {
        g_task_return_new_error(req->task, POLKIT_ERROR, POLKIT_ERROR_CANCELLED, "Authentication request was cancelled");
    }

    finish_request(req);
    return G_SOURCE_REMOVE;
}

static void on_cancellable_cancelled(GCancellable *cancellable, gpointer user_data) {
    (void)cancellable;
    AuthRequest *req = (AuthRequest *)user_data;
    if (req->completed) return;
    req->cancellable_id = 0;
    g_main_context_invoke(NULL, do_cancellable_cancel, req);
}

static void on_session_request(PolkitAgentSession *session,
                               gchar              *request_str,
                               gboolean            echo_on,
                               gpointer            user_data)
{
    AuthRequest *req = (AuthRequest *)user_data;
    if (req->completed) return;

    if (req->timeout_id != 0) {
        g_source_remove(req->timeout_id);
        req->timeout_id = 0;
    }

    if (req->pending_password != NULL) {
        gchar *queued = req->pending_password;
        req->pending_password = NULL;
        req->awaiting_request = FALSE;
        req->in_progress = TRUE;
        worker_send_text_cmd(req, "INFO", "Verifying credentials...");
        arm_auth_timeout(req, 12);
        polkit_agent_session_response(session, queued);
        explicit_bzero(queued, strlen(queued));
        g_free(queued);
        return;
    }

    req->awaiting_request = TRUE;
    req->in_progress = FALSE;

    worker_send_text_cmd(req, "INFO", "");
    worker_send_prompt(req, request_str, echo_on);
    worker_send_sensitive(req, TRUE);
    worker_send_line(req, "FOCUS\n");
}

static void on_session_show_error(PolkitAgentSession *session,
                                  gchar              *text,
                                  gpointer            user_data)
{
    (void)session;
    AuthRequest *req = (AuthRequest *)user_data;
    if (req->completed) return;
    worker_send_text_cmd(req, "ERROR", text);
}

static void on_session_show_info(PolkitAgentSession *session,
                                 gchar              *text,
                                 gpointer            user_data)
{
    (void)session;
    AuthRequest *req = (AuthRequest *)user_data;
    if (req->completed) return;
    if (req->pending_password == NULL) {
        worker_send_text_cmd(req, "INFO", text);
    }
}

static void on_session_completed(PolkitAgentSession *session,
                                 gboolean            gained_authorization,
                                 gpointer            user_data)
{
    (void)session;
    AuthRequest *req = (AuthRequest *)user_data;
    if (req->completed) return;

    if (req->timeout_id != 0) {
        g_source_remove(req->timeout_id);
        req->timeout_id = 0;
    }
    req->in_progress = FALSE;
    req->awaiting_request = FALSE;
    clear_pending_password(req);

    if (gained_authorization) {
        req->completed = TRUE;
        if (req->task != NULL && !g_task_get_completed(req->task)) {
            g_task_return_boolean(req->task, TRUE);
        }
        finish_request(req);
    } else if (req->cancellable != NULL && g_cancellable_is_cancelled(req->cancellable)) {
        req->completed = TRUE;
        if (req->task != NULL && !g_task_get_completed(req->task)) {
            g_task_return_new_error(req->task, POLKIT_ERROR, POLKIT_ERROR_CANCELLED, "Authentication cancelled");
        }
        finish_request(req);
    } else {
        worker_send_text_cmd(req, "INFO", "");
        worker_send_text_cmd(req, "ERROR", "Authentication failed. Please try again.");
        worker_send_line(req, "CLEAR\n");
        worker_send_sensitive(req, TRUE);
        worker_send_line(req, "FOCUS\n");
        start_session(req);
    }
}

static void start_session(AuthRequest *req) {
    disconnect_session(req);
    clear_pending_password(req);
    req->awaiting_request = FALSE;

    if (req->selected_identity == NULL) {
        if (req->identities != NULL && req->identities->data != NULL) {
            req->selected_identity = POLKIT_IDENTITY(req->identities->data);
        } else {
            PolkitIdentity *current_user = polkit_unix_user_new(getuid());
            req->identities = g_list_append(NULL, current_user);
            req->selected_identity = current_user;
        }
    }

    req->session = polkit_agent_session_new(req->selected_identity, req->cookie);
    g_signal_connect(req->session, "request", G_CALLBACK(on_session_request), req);
    g_signal_connect(req->session, "show-error", G_CALLBACK(on_session_show_error), req);
    g_signal_connect(req->session, "show-info", G_CALLBACK(on_session_show_info), req);
    g_signal_connect(req->session, "completed", G_CALLBACK(on_session_completed), req);

    polkit_agent_session_initiate(req->session);
}

static void finish_request(AuthRequest *req) {
    if (req->timeout_id != 0) {
        g_source_remove(req->timeout_id);
        req->timeout_id = 0;
    }

    clear_pending_password(req);
    close_worker(req);

    if (req->cancellable != NULL && req->cancellable_id != 0) {
        gulong cid = req->cancellable_id;
        req->cancellable_id = 0;
        g_cancellable_disconnect(req->cancellable, cid);
    }

    disconnect_session(req);

    if (req->task != NULL) {
        g_object_unref(req->task);
        req->task = NULL;
    }

    if (req->cancellable != NULL) {
        g_object_unref(req->cancellable);
        req->cancellable = NULL;
    }

    g_free(req->action_id);
    g_free(req->message);
    g_free(req->icon_name);
    g_free(req->cookie);

    if (req->identities != NULL) {
        g_list_free_full(req->identities, g_object_unref);
        req->identities = NULL;
    }

    g_free(req);
    malloc_trim(0);
}

static const char *SYS_POLKIT_SOURCE_TAG = "sys-polkit-initiate-auth";

static gpointer copy_gobject(gconstpointer src, gpointer user_data) {
    (void)user_data;
    return g_object_ref((gpointer)src);
}

static void sys_polkit_listener_initiate_authentication(PolkitAgentListener  *listener,
                                                        const gchar          *action_id,
                                                        const gchar          *message,
                                                        const gchar          *icon_name,
                                                        PolkitDetails        *details,
                                                        const gchar          *cookie,
                                                        GList                *identities,
                                                        GCancellable         *cancellable,
                                                        GAsyncReadyCallback   callback,
                                                        gpointer              user_data)
{
    (void)details;

    AuthRequest *req = g_new0(AuthRequest, 1);
    req->listener = SYS_POLKIT_LISTENER(listener);
    req->worker_in_fd = -1;
    req->task = g_task_new(listener, cancellable, callback, user_data);
    g_task_set_source_tag(req->task, (gpointer)SYS_POLKIT_SOURCE_TAG);

    req->action_id = g_strdup(action_id);
    req->message = g_strdup(message);
    req->icon_name = g_strdup(icon_name);
    req->cookie = g_strdup(cookie);

    if (identities != NULL) {
        req->identities = g_list_copy_deep(identities, copy_gobject, NULL);
        uid_t current_uid = getuid();
        req->selected_identity = POLKIT_IDENTITY(req->identities->data);
        for (GList *l = req->identities; l != NULL; l = l->next) {
            PolkitIdentity *id = POLKIT_IDENTITY(l->data);
            if (POLKIT_IS_UNIX_USER(id) && (uid_t)polkit_unix_user_get_uid(POLKIT_UNIX_USER(id)) == current_uid) {
                req->selected_identity = id;
                break;
            }
        }
    } else {
        PolkitIdentity *current_user = polkit_unix_user_new(getuid());
        req->identities = g_list_append(NULL, current_user);
        req->selected_identity = current_user;
    }

    if (cancellable != NULL) {
        req->cancellable = g_object_ref(cancellable);
        if (g_cancellable_is_cancelled(cancellable)) {
            req->completed = TRUE;
            g_task_return_new_error(req->task, POLKIT_ERROR, POLKIT_ERROR_CANCELLED, "Authentication request was cancelled");
            finish_request(req);
            return;
        }
        req->cancellable_id = g_cancellable_connect(cancellable,
                                                   G_CALLBACK(on_cancellable_cancelled),
                                                   req,
                                                   NULL);
    }

    if (!spawn_dialog_worker(req)) {
        req->completed = TRUE;
        g_task_return_new_error(req->task, POLKIT_ERROR, POLKIT_ERROR_FAILED, "Failed to launch authentication dialog");
        finish_request(req);
        return;
    }

    start_session(req);
}

static gboolean sys_polkit_listener_initiate_authentication_finish(PolkitAgentListener  *listener,
                                                                   GAsyncResult         *res,
                                                                   GError              **error)
{
    (void)listener;
    g_return_val_if_fail(g_task_is_valid(res, listener), FALSE);
    return g_task_propagate_boolean(G_TASK(res), error);
}

static void sys_polkit_listener_finalize(GObject *object) {
    G_OBJECT_CLASS(sys_polkit_listener_parent_class)->finalize(object);
}

static void sys_polkit_listener_class_init(SysPolkitListenerClass *klass) {
    GObjectClass *g_object_class = G_OBJECT_CLASS(klass);
    g_object_class->finalize = sys_polkit_listener_finalize;

    PolkitAgentListenerClass *pkal_class = POLKIT_AGENT_LISTENER_CLASS(klass);
    pkal_class->initiate_authentication = sys_polkit_listener_initiate_authentication;
    pkal_class->initiate_authentication_finish = sys_polkit_listener_initiate_authentication_finish;
}

static void sys_polkit_listener_init(SysPolkitListener *self) {
    (void)self;
}

PolkitAgentListener *sys_polkit_listener_new(void) {
    return g_object_new(SYS_POLKIT_TYPE_LISTENER, NULL);
}
