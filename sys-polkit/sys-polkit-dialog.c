#include "sys-polkit-dialog.h"
#include <pwd.h>
#include <grp.h>
#include <unistd.h>
#include <gdk/gdkkeysyms.h>

struct _SysPolkitDialog {
    GtkWidget *window;
    GtkWidget *icon_widget;
    GtkWidget *title_label;
    GtkWidget *message_label;
    GtkWidget *action_label;
    GtkWidget *identity_box;
    GtkWidget *identity_combo;
    GtkWidget *identity_single_label;
    GtkWidget *prompt_label;
    GtkWidget *entry;
    GtkWidget *error_label;
    GtkWidget *btn_cancel;
    GtkWidget *btn_auth;

    GList *identities;
    PolkitIdentity *selected_identity;

    SysPolkitDialogCallbacks callbacks;
};

static const char *CATPPUCCIN_CSS =
"window.sys-polkit-window {\n"
"    background-color: #1e1e2e;\n"
"    border: 2px solid #cba6f7;\n"
"    border-radius: 14px;\n"
"}\n"
".auth-card {\n"
"    padding: 22px 24px;\n"
"    background-color: #1e1e2e;\n"
"}\n"
".auth-title {\n"
"    font-family: 'JetBrainsMono Nerd Font', 'Noto Sans', sans-serif;\n"
"    font-size: 13pt;\n"
"    font-weight: 800;\n"
"    color: #cdd6f4;\n"
"}\n"
".auth-message {\n"
"    font-family: 'JetBrainsMono Nerd Font', 'Noto Sans', sans-serif;\n"
"    font-size: 10pt;\n"
"    color: #bac2de;\n"
"}\n"
".auth-action-id {\n"
"    font-family: 'JetBrainsMono Nerd Font', monospace;\n"
"    font-size: 8.5pt;\n"
"    color: #6c7086;\n"
"    margin-top: 2px;\n"
"}\n"
".auth-id-header {\n"
"    font-family: 'JetBrainsMono Nerd Font', sans-serif;\n"
"    font-size: 9.5pt;\n"
"    font-weight: 600;\n"
"    color: #89b4fa;\n"
"}\n"
".auth-id-badge {\n"
"    font-family: 'JetBrainsMono Nerd Font', monospace;\n"
"    font-size: 9.5pt;\n"
"    font-weight: 700;\n"
"    color: #b4befe;\n"
"    background-color: #313244;\n"
"    border-radius: 6px;\n"
"    padding: 3px 10px;\n"
"}\n"
".auth-prompt-label {\n"
"    font-family: 'JetBrainsMono Nerd Font', sans-serif;\n"
"    font-size: 9pt;\n"
"    font-weight: 600;\n"
"    color: #a6adc8;\n"
"    margin-bottom: 2px;\n"
"}\n"
"entry.auth-entry {\n"
"    background-color: #181825;\n"
"    border: 1.5px solid #45475a;\n"
"    border-radius: 8px;\n"
"    color: #cdd6f4;\n"
"    font-family: 'JetBrainsMono Nerd Font', monospace;\n"
"    font-size: 11pt;\n"
"    padding: 8px 12px;\n"
"    caret-color: #cba6f7;\n"
"}\n"
"entry.auth-entry:selected {\n"
"    background-color: #585b70;\n"
"    color: #cdd6f4;\n"
"}\n"
"entry.auth-entry:focus {\n"
"    border-color: #cba6f7;\n"
"}\n"
".auth-error {\n"
"    font-family: 'JetBrainsMono Nerd Font', sans-serif;\n"
"    font-size: 9.5pt;\n"
"    font-weight: 700;\n"
"    color: #f38ba8;\n"
"    margin-top: 4px;\n"
"    margin-bottom: 2px;\n"
"}\n"
"button.btn-cancel {\n"
"    background-color: #313244;\n"
"    color: #cdd6f4;\n"
"    font-family: 'JetBrainsMono Nerd Font', sans-serif;\n"
"    font-size: 10pt;\n"
"    font-weight: 600;\n"
"    border-radius: 8px;\n"
"    border: 1px solid #45475a;\n"
"    padding: 7px 18px;\n"
"}\n"
"button.btn-cancel:hover {\n"
"    background-color: #45475a;\n"
"    color: #ffffff;\n"
"}\n"
"button.btn-auth {\n"
"    background-color: #cba6f7;\n"
"    color: #11111b;\n"
"    font-family: 'JetBrainsMono Nerd Font', sans-serif;\n"
"    font-size: 10pt;\n"
"    font-weight: 700;\n"
"    border-radius: 8px;\n"
"    border: 1px solid #cba6f7;\n"
"    padding: 7px 22px;\n"
"}\n"
"button.btn-auth:hover {\n"
"    background-color: #b4befe;\n"
"    border-color: #b4befe;\n"
"}\n"
"button.btn-auth:disabled, entry.auth-entry:disabled {\n"
"    opacity: 0.6;\n"
"}\n"
"combobox button {\n"
"    background-color: #181825;\n"
"    border: 1.5px solid #45475a;\n"
"    border-radius: 6px;\n"
"    color: #cdd6f4;\n"
"    padding: 4px 10px;\n"
"}\n";

static gboolean s_styles_initialized = FALSE;

void sys_polkit_dialog_init_styles(void) {
    if (s_styles_initialized) {
        return;
    }
    GtkCssProvider *provider = gtk_css_provider_new();
    gtk_css_provider_load_from_data(provider, CATPPUCCIN_CSS, -1, NULL);
    gtk_style_context_add_provider_for_screen(
        gdk_screen_get_default(),
        GTK_STYLE_PROVIDER(provider),
        GTK_STYLE_PROVIDER_PRIORITY_APPLICATION
    );
    g_object_unref(provider);
    s_styles_initialized = TRUE;
}

static gchar *get_identity_display_name(PolkitIdentity *identity) {
    if (POLKIT_IS_UNIX_USER(identity)) {
        uid_t uid = (uid_t)polkit_unix_user_get_uid(POLKIT_UNIX_USER(identity));
        struct passwd *pw = getpwuid(uid);
        if (pw != NULL) {
            if (pw->pw_gecos != NULL && pw->pw_gecos[0] != '\0' && g_strcmp0(pw->pw_gecos, pw->pw_name) != 0) {
                return g_strdup_printf("%s (%s)", pw->pw_name, pw->pw_gecos);
            }
            return g_strdup(pw->pw_name);
        }
    } else if (POLKIT_IS_UNIX_GROUP(identity)) {
        gid_t gid = (gid_t)polkit_unix_group_get_gid(POLKIT_UNIX_GROUP(identity));
        struct group *gr = getgrgid(gid);
        if (gr != NULL) {
            return g_strdup_printf("Group: %s", gr->gr_name);
        }
    }
    return polkit_identity_to_string(identity);
}

static void on_entry_activate(GtkEntry *entry, gpointer user_data) {
    SysPolkitDialog *dlg = (SysPolkitDialog *)user_data;
    (void)entry;
    if (dlg->callbacks.on_submit != NULL) {
        const gchar *pass = gtk_entry_get_text(GTK_ENTRY(dlg->entry));
        dlg->callbacks.on_submit(pass, dlg->callbacks.user_data);
    }
}

static void on_btn_auth_clicked(GtkButton *btn, gpointer user_data) {
    SysPolkitDialog *dlg = (SysPolkitDialog *)user_data;
    (void)btn;
    if (dlg->callbacks.on_submit != NULL) {
        const gchar *pass = gtk_entry_get_text(GTK_ENTRY(dlg->entry));
        dlg->callbacks.on_submit(pass, dlg->callbacks.user_data);
    }
}

static void on_btn_cancel_clicked(GtkButton *btn, gpointer user_data) {
    SysPolkitDialog *dlg = (SysPolkitDialog *)user_data;
    (void)btn;
    if (dlg->callbacks.on_cancel != NULL) {
        dlg->callbacks.on_cancel(dlg->callbacks.user_data);
    }
}

static gboolean on_window_key_press(GtkWidget *widget, GdkEventKey *event, gpointer user_data) {
    SysPolkitDialog *dlg = (SysPolkitDialog *)user_data;
    (void)widget;
    if (event->keyval == GDK_KEY_Escape) {
        if (dlg->callbacks.on_cancel != NULL) {
            dlg->callbacks.on_cancel(dlg->callbacks.user_data);
        }
        return GDK_EVENT_STOP;
    }
    return GDK_EVENT_PROPAGATE;
}

static gboolean on_window_delete_event(GtkWidget *widget, GdkEvent *event, gpointer user_data) {
    SysPolkitDialog *dlg = (SysPolkitDialog *)user_data;
    (void)widget;
    (void)event;
    if (dlg->callbacks.on_cancel != NULL) {
        dlg->callbacks.on_cancel(dlg->callbacks.user_data);
    }
    return TRUE;
}

static void on_combo_changed(GtkComboBox *combo, gpointer user_data) {
    SysPolkitDialog *dlg = (SysPolkitDialog *)user_data;
    GtkTreeIter iter;
    GtkTreeModel *model = gtk_combo_box_get_model(combo);

    if (!gtk_combo_box_get_active_iter(combo, &iter)) {
        return;
    }

    PolkitIdentity *identity = NULL;
    gtk_tree_model_get(model, &iter, 1, &identity, -1);
    if (identity != NULL) {
        dlg->selected_identity = identity;
        if (dlg->callbacks.on_identity_changed != NULL) {
            dlg->callbacks.on_identity_changed(identity, dlg->callbacks.user_data);
        }
        g_object_unref(identity);
    }
}

SysPolkitDialog *sys_polkit_dialog_new(const gchar                    *action_id,
                                       const gchar                    *message,
                                       const gchar                    *icon_name,
                                       PolkitDetails                  *details,
                                       GList                          *identities,
                                       const SysPolkitDialogCallbacks *callbacks)
{
    (void)details;
    sys_polkit_dialog_init_styles();

    SysPolkitDialog *dlg = g_new0(SysPolkitDialog, 1);
    dlg->callbacks = *callbacks;
    dlg->identities = identities;

    /* Create Toplevel Window */
    dlg->window = gtk_window_new(GTK_WINDOW_TOPLEVEL);
    gtk_window_set_title(GTK_WINDOW(dlg->window), "Authentication Required");
    gtk_window_set_role(GTK_WINDOW(dlg->window), SYS_POLKIT_WM_CLASS);
    gtk_window_set_position(GTK_WINDOW(dlg->window), GTK_WIN_POS_CENTER_ALWAYS);
    gtk_window_set_default_size(GTK_WINDOW(dlg->window), 450, 260);
    gtk_window_set_resizable(GTK_WINDOW(dlg->window), FALSE);
    gtk_window_set_type_hint(GTK_WINDOW(dlg->window), GDK_WINDOW_TYPE_HINT_DIALOG);
    gtk_window_set_modal(GTK_WINDOW(dlg->window), TRUE);
    gtk_window_set_keep_above(GTK_WINDOW(dlg->window), TRUE);
    gtk_window_set_skip_taskbar_hint(GTK_WINDOW(dlg->window), TRUE);
    gtk_window_set_skip_pager_hint(GTK_WINDOW(dlg->window), TRUE);

    GtkStyleContext *win_ctx = gtk_widget_get_style_context(dlg->window);
    gtk_style_context_add_class(win_ctx, "sys-polkit-window");

    g_signal_connect(dlg->window, "key-press-event", G_CALLBACK(on_window_key_press), dlg);
    g_signal_connect(dlg->window, "delete-event", G_CALLBACK(on_window_delete_event), dlg);

    /* Main Box */
    GtkWidget *main_box = gtk_box_new(GTK_ORIENTATION_VERTICAL, 14);
    GtkStyleContext *card_ctx = gtk_widget_get_style_context(main_box);
    gtk_style_context_add_class(card_ctx, "auth-card");
    gtk_container_add(GTK_CONTAINER(dlg->window), main_box);

    /* Header Row (Icon + Title & Description) */
    GtkWidget *header_box = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 16);
    gtk_box_pack_start(GTK_BOX(main_box), header_box, FALSE, FALSE, 0);

    /* Icon */
    const gchar *chosen_icon = (icon_name != NULL && icon_name[0] != '\0') ? icon_name : "dialog-password";
    if (!gtk_icon_theme_has_icon(gtk_icon_theme_get_default(), chosen_icon)) {
        if (gtk_icon_theme_has_icon(gtk_icon_theme_get_default(), "security-high")) {
            chosen_icon = "security-high";
        } else if (gtk_icon_theme_has_icon(gtk_icon_theme_get_default(), "system-lock-screen")) {
            chosen_icon = "system-lock-screen";
        }
    }
    dlg->icon_widget = gtk_image_new_from_icon_name(chosen_icon, GTK_ICON_SIZE_DIALOG);
    gtk_image_set_pixel_size(GTK_IMAGE(dlg->icon_widget), 48);
    gtk_widget_set_valign(dlg->icon_widget, GTK_ALIGN_START);
    gtk_box_pack_start(GTK_BOX(header_box), dlg->icon_widget, FALSE, FALSE, 0);

    /* Header text vbox */
    GtkWidget *text_box = gtk_box_new(GTK_ORIENTATION_VERTICAL, 4);
    gtk_box_pack_start(GTK_BOX(header_box), text_box, TRUE, TRUE, 0);

    dlg->title_label = gtk_label_new("Authentication Required");
    gtk_widget_set_halign(dlg->title_label, GTK_ALIGN_START);
    GtkStyleContext *title_ctx = gtk_widget_get_style_context(dlg->title_label);
    gtk_style_context_add_class(title_ctx, "auth-title");
    gtk_box_pack_start(GTK_BOX(text_box), dlg->title_label, FALSE, FALSE, 0);

    const gchar *msg_text = (message != NULL && message[0] != '\0')
        ? message
        : "An application is attempting to perform an action that requires administrative privileges.";
    dlg->message_label = gtk_label_new(msg_text);
    gtk_widget_set_halign(dlg->message_label, GTK_ALIGN_START);
    gtk_label_set_line_wrap(GTK_LABEL(dlg->message_label), TRUE);
    gtk_label_set_line_wrap_mode(GTK_LABEL(dlg->message_label), PANGO_WRAP_WORD_CHAR);
    gtk_label_set_max_width_chars(GTK_LABEL(dlg->message_label), 46);
    GtkStyleContext *msg_ctx = gtk_widget_get_style_context(dlg->message_label);
    gtk_style_context_add_class(msg_ctx, "auth-message");
    gtk_box_pack_start(GTK_BOX(text_box), dlg->message_label, FALSE, FALSE, 0);

    if (action_id != NULL && action_id[0] != '\0') {
        gchar *action_str = g_strdup_printf("Action: %s", action_id);
        dlg->action_label = gtk_label_new(action_str);
        g_free(action_str);
        gtk_widget_set_halign(dlg->action_label, GTK_ALIGN_START);
        GtkStyleContext *act_ctx = gtk_widget_get_style_context(dlg->action_label);
        gtk_style_context_add_class(act_ctx, "auth-action-id");
        gtk_box_pack_start(GTK_BOX(text_box), dlg->action_label, FALSE, FALSE, 0);
    }

    /* Identity section */
    dlg->identity_box = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 10);
    gtk_box_pack_start(GTK_BOX(main_box), dlg->identity_box, FALSE, FALSE, 0);

    GtkWidget *lbl_id_hdr = gtk_label_new("Authenticating as:");
    GtkStyleContext *hdr_ctx = gtk_widget_get_style_context(lbl_id_hdr);
    gtk_style_context_add_class(hdr_ctx, "auth-id-header");
    gtk_box_pack_start(GTK_BOX(dlg->identity_box), lbl_id_hdr, FALSE, FALSE, 0);

    guint num_identities = (identities != NULL) ? g_list_length(identities) : 0;
    uid_t current_uid = getuid();
    gint active_index = 0;

    if (num_identities > 1) {
        GtkListStore *store = gtk_list_store_new(2, G_TYPE_STRING, G_TYPE_OBJECT);
        GtkTreeIter iter;
        gint idx = 0;

        for (GList *l = identities; l != NULL; l = l->next, idx++) {
            PolkitIdentity *id = POLKIT_IDENTITY(l->data);
            gchar *display_name = get_identity_display_name(id);
            gtk_list_store_append(store, &iter);
            gtk_list_store_set(store, &iter, 0, display_name, 1, id, -1);
            g_free(display_name);

            if (POLKIT_IS_UNIX_USER(id) && (uid_t)polkit_unix_user_get_uid(POLKIT_UNIX_USER(id)) == current_uid) {
                active_index = idx;
            }
        }

        dlg->identity_combo = gtk_combo_box_new_with_model(GTK_TREE_MODEL(store));
        g_object_unref(store);

        GtkCellRenderer *renderer = gtk_cell_renderer_text_new();
        gtk_cell_layout_pack_start(GTK_CELL_LAYOUT(dlg->identity_combo), renderer, TRUE);
        gtk_cell_layout_set_attributes(GTK_CELL_LAYOUT(dlg->identity_combo), renderer, "text", 0, NULL);

        g_signal_connect(dlg->identity_combo, "changed", G_CALLBACK(on_combo_changed), dlg);
        gtk_combo_box_set_active(GTK_COMBO_BOX(dlg->identity_combo), active_index);
        gtk_box_pack_start(GTK_BOX(dlg->identity_box), dlg->identity_combo, TRUE, TRUE, 0);
    } else if (num_identities == 1) {
        PolkitIdentity *id = POLKIT_IDENTITY(identities->data);
        dlg->selected_identity = id;
        gchar *display_name = get_identity_display_name(id);
        dlg->identity_single_label = gtk_label_new(display_name);
        g_free(display_name);
        GtkStyleContext *b_ctx = gtk_widget_get_style_context(dlg->identity_single_label);
        gtk_style_context_add_class(b_ctx, "auth-id-badge");
        gtk_box_pack_start(GTK_BOX(dlg->identity_box), dlg->identity_single_label, FALSE, FALSE, 0);
    } else {
        /* Default to current user */
        struct passwd *pw = getpwuid(current_uid);
        const gchar *uname = (pw != NULL) ? pw->pw_name : "root";
        dlg->identity_single_label = gtk_label_new(uname);
        GtkStyleContext *b_ctx = gtk_widget_get_style_context(dlg->identity_single_label);
        gtk_style_context_add_class(b_ctx, "auth-id-badge");
        gtk_box_pack_start(GTK_BOX(dlg->identity_box), dlg->identity_single_label, FALSE, FALSE, 0);
    }

    /* Prompt label */
    dlg->prompt_label = gtk_label_new("Password:");
    gtk_widget_set_halign(dlg->prompt_label, GTK_ALIGN_START);
    GtkStyleContext *p_ctx = gtk_widget_get_style_context(dlg->prompt_label);
    gtk_style_context_add_class(p_ctx, "auth-prompt-label");
    gtk_box_pack_start(GTK_BOX(main_box), dlg->prompt_label, FALSE, FALSE, 0);

    /* Entry */
    dlg->entry = gtk_entry_new();
    gtk_entry_set_visibility(GTK_ENTRY(dlg->entry), FALSE);
    gtk_entry_set_invisible_char(GTK_ENTRY(dlg->entry), 0x25CF); /* Unicode ● */
    gtk_entry_set_placeholder_text(GTK_ENTRY(dlg->entry), "Enter password...");
    GtkStyleContext *ent_ctx = gtk_widget_get_style_context(dlg->entry);
    gtk_style_context_add_class(ent_ctx, "auth-entry");
    g_signal_connect(dlg->entry, "activate", G_CALLBACK(on_entry_activate), dlg);
    gtk_box_pack_start(GTK_BOX(main_box), dlg->entry, FALSE, FALSE, 0);

    /* Error Label */
    dlg->error_label = gtk_label_new("");
    gtk_widget_set_halign(dlg->error_label, GTK_ALIGN_START);
    GtkStyleContext *err_ctx = gtk_widget_get_style_context(dlg->error_label);
    gtk_style_context_add_class(err_ctx, "auth-error");
    gtk_widget_set_no_show_all(dlg->error_label, TRUE);
    gtk_box_pack_start(GTK_BOX(main_box), dlg->error_label, FALSE, FALSE, 0);

    /* Button Row */
    GtkWidget *btn_box = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 12);
    gtk_widget_set_halign(btn_box, GTK_ALIGN_END);
    gtk_box_pack_start(GTK_BOX(main_box), btn_box, FALSE, FALSE, 4);

    dlg->btn_cancel = gtk_button_new_with_label("Cancel");
    GtkStyleContext *can_ctx = gtk_widget_get_style_context(dlg->btn_cancel);
    gtk_style_context_add_class(can_ctx, "btn-cancel");
    g_signal_connect(dlg->btn_cancel, "clicked", G_CALLBACK(on_btn_cancel_clicked), dlg);
    gtk_box_pack_start(GTK_BOX(btn_box), dlg->btn_cancel, FALSE, FALSE, 0);

    dlg->btn_auth = gtk_button_new_with_label("Authenticate");
    GtkStyleContext *aut_ctx = gtk_widget_get_style_context(dlg->btn_auth);
    gtk_style_context_add_class(aut_ctx, "btn-auth");
    g_signal_connect(dlg->btn_auth, "clicked", G_CALLBACK(on_btn_auth_clicked), dlg);
    gtk_box_pack_start(GTK_BOX(btn_box), dlg->btn_auth, FALSE, FALSE, 0);

    gtk_widget_show_all(main_box);

    return dlg;
}

void sys_polkit_dialog_show(SysPolkitDialog *dialog) {
    if (dialog == NULL || dialog->window == NULL) return;
    gtk_widget_show_all(dialog->window);
    gtk_widget_grab_focus(dialog->entry);
    gtk_window_present(GTK_WINDOW(dialog->window));
}

void sys_polkit_dialog_set_error(SysPolkitDialog *dialog, const gchar *error_msg) {
    if (dialog == NULL || dialog->error_label == NULL) return;
    if (error_msg != NULL && error_msg[0] != '\0') {
        gtk_label_set_text(GTK_LABEL(dialog->error_label), error_msg);
        gtk_widget_set_no_show_all(dialog->error_label, FALSE);
        gtk_widget_show(dialog->error_label);
    } else {
        gtk_label_set_text(GTK_LABEL(dialog->error_label), "");
        gtk_widget_hide(dialog->error_label);
    }
}

void sys_polkit_dialog_set_prompt(SysPolkitDialog *dialog, const gchar *prompt, gboolean echo_on) {
    if (dialog == NULL) return;
    if (prompt != NULL && prompt[0] != '\0') {
        gtk_label_set_text(GTK_LABEL(dialog->prompt_label), prompt);
        gtk_entry_set_placeholder_text(GTK_ENTRY(dialog->entry), prompt);
    }
    gtk_entry_set_visibility(GTK_ENTRY(dialog->entry), echo_on);
}

void sys_polkit_dialog_set_sensitive(SysPolkitDialog *dialog, gboolean sensitive) {
    if (dialog == NULL) return;
    gtk_widget_set_sensitive(dialog->entry, sensitive);
    gtk_widget_set_sensitive(dialog->btn_auth, sensitive);
    if (dialog->identity_combo != NULL) {
        gtk_widget_set_sensitive(dialog->identity_combo, sensitive);
    }
}

void sys_polkit_dialog_clear_entry(SysPolkitDialog *dialog) {
    if (dialog == NULL || dialog->entry == NULL) return;
    gtk_entry_set_text(GTK_ENTRY(dialog->entry), "");
}

void sys_polkit_dialog_focus_entry(SysPolkitDialog *dialog) {
    if (dialog == NULL || dialog->entry == NULL) return;
    gtk_widget_grab_focus(dialog->entry);
}

PolkitIdentity *sys_polkit_dialog_get_selected_identity(SysPolkitDialog *dialog) {
    if (dialog == NULL) return NULL;
    return dialog->selected_identity;
}

GtkWidget *sys_polkit_dialog_get_window(SysPolkitDialog *dialog) {
    if (dialog == NULL) return NULL;
    return dialog->window;
}

void sys_polkit_dialog_destroy(SysPolkitDialog *dialog) {
    if (dialog == NULL) return;
    if (dialog->window != NULL) {
        gtk_widget_destroy(dialog->window);
        dialog->window = NULL;
    }
    g_free(dialog);
}
