#include "sys-polkit-dialog.h"
#include <pwd.h>
#include <grp.h>
#include <stdio.h>
#include <string.h>
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
    GtkWidget *info_label;
    GtkWidget *error_label;
    GtkWidget *btn_cancel;
    GtkWidget *btn_auth;

    GList *identities;
    PolkitIdentity *selected_identity;

    SysPolkitDialogCallbacks callbacks;
};

static const char *CATPPUCCIN_CSS =
"window.sys-polkit-window {\n"
"    background-color: #181a2c;\n"
"    border: 2px solid #f7b277;\n"
"    border-radius: 10px;\n"
"}\n"
".auth-card {\n"
"    padding: 14px 16px;\n"
"    background-color: #181a2c;\n"
"}\n"
".auth-title {\n"
"    font-family: 'JetBrainsMono Nerd Font', 'Noto Sans', sans-serif;\n"
"    font-size: 11pt;\n"
"    font-weight: 800;\n"
"    color: #f3e6dc;\n"
"}\n"
".auth-message {\n"
"    font-family: 'JetBrainsMono Nerd Font', 'Noto Sans', sans-serif;\n"
"    font-size: 9pt;\n"
"    color: #b8adc4;\n"
"}\n"
".auth-action-id {\n"
"    font-family: 'JetBrainsMono Nerd Font', monospace;\n"
"    font-size: 8pt;\n"
"    color: #7c6d8a;\n"
"    margin-top: 1px;\n"
"}\n"
".auth-id-header {\n"
"    font-family: 'JetBrainsMono Nerd Font', sans-serif;\n"
"    font-size: 8.5pt;\n"
"    font-weight: 600;\n"
"    color: #8ecae6;\n"
"}\n"
".auth-id-badge {\n"
"    font-family: 'JetBrainsMono Nerd Font', monospace;\n"
"    font-size: 8.5pt;\n"
"    font-weight: 700;\n"
"    color: #f7b277;\n"
"    background-color: #23243b;\n"
"    border-radius: 5px;\n"
"    padding: 2px 8px;\n"
"}\n"
".auth-prompt-label {\n"
"    font-family: 'JetBrainsMono Nerd Font', sans-serif;\n"
"    font-size: 8.5pt;\n"
"    font-weight: 600;\n"
"    color: #b8adc4;\n"
"    margin-bottom: 1px;\n"
"}\n"
"entry.auth-entry {\n"
"    background-color: #131523;\n"
"    border: 1.5px solid #343252;\n"
"    border-radius: 7px;\n"
"    color: #f3e6dc;\n"
"    font-family: 'JetBrainsMono Nerd Font', monospace;\n"
"    font-size: 9.5pt;\n"
"    padding: 6px 10px;\n"
"    caret-color: #f7b277;\n"
"}\n"
"entry.auth-entry:selected {\n"
"    background-color: #343252;\n"
"    color: #f3e6dc;\n"
"}\n"
"entry.auth-entry:focus {\n"
"    border-color: #f7b277;\n"
"}\n"
".auth-info {\n"
"    font-family: 'JetBrainsMono Nerd Font', sans-serif;\n"
"    font-size: 8.5pt;\n"
"    font-weight: 600;\n"
"    color: #8ecae6;\n"
"    margin-top: 2px;\n"
"}\n"
".auth-error {\n"
"    font-family: 'JetBrainsMono Nerd Font', sans-serif;\n"
"    font-size: 8.5pt;\n"
"    font-weight: 700;\n"
"    color: #eb6f7c;\n"
"    margin-top: 2px;\n"
"}\n"
"button.btn-cancel {\n"
"    background-color: #23243b;\n"
"    color: #f3e6dc;\n"
"    font-family: 'JetBrainsMono Nerd Font', sans-serif;\n"
"    font-size: 9pt;\n"
"    font-weight: 600;\n"
"    border-radius: 7px;\n"
"    border: 1px solid #343252;\n"
"    padding: 5px 14px;\n"
"}\n"
"button.btn-cancel:hover {\n"
"    background-color: #343252;\n"
"    color: #fcf4eb;\n"
"}\n"
"button.btn-auth {\n"
"    background-color: #f7b277;\n"
"    color: #131523;\n"
"    font-family: 'JetBrainsMono Nerd Font', sans-serif;\n"
"    font-size: 9pt;\n"
"    font-weight: 700;\n"
"    border-radius: 7px;\n"
"    border: 1px solid #f7b277;\n"
"    padding: 5px 16px;\n"
"}\n"
"button.btn-auth:hover {\n"
"    background-color: #f9d68b;\n"
"    border-color: #f9d68b;\n"
"}\n"
"button.btn-auth:disabled, entry.auth-entry:disabled {\n"
"    opacity: 0.6;\n"
"}\n"
"combobox button {\n"
"    background-color: #131523;\n"
"    border: 1.5px solid #343252;\n"
"    border-radius: 6px;\n"
"    color: #f3e6dc;\n"
"    padding: 3px 8px;\n"
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
    gtk_window_set_default_size(GTK_WINDOW(dlg->window), 360, -1);
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
    GtkWidget *main_box = gtk_box_new(GTK_ORIENTATION_VERTICAL, 8);
    GtkStyleContext *card_ctx = gtk_widget_get_style_context(main_box);
    gtk_style_context_add_class(card_ctx, "auth-card");
    gtk_container_add(GTK_CONTAINER(dlg->window), main_box);

    /* Header Row (Icon + Title & Description) */
    GtkWidget *header_box = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 12);
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
    dlg->icon_widget = gtk_image_new_from_icon_name(chosen_icon, GTK_ICON_SIZE_DND);
    gtk_image_set_pixel_size(GTK_IMAGE(dlg->icon_widget), 32);
    gtk_widget_set_valign(dlg->icon_widget, GTK_ALIGN_START);
    gtk_box_pack_start(GTK_BOX(header_box), dlg->icon_widget, FALSE, FALSE, 0);

    /* Header text vbox */
    GtkWidget *text_box = gtk_box_new(GTK_ORIENTATION_VERTICAL, 3);
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
    gtk_label_set_max_width_chars(GTK_LABEL(dlg->message_label), 40);
    gtk_label_set_lines(GTK_LABEL(dlg->message_label), 3);
    gtk_label_set_ellipsize(GTK_LABEL(dlg->message_label), PANGO_ELLIPSIZE_END);
    GtkStyleContext *msg_ctx = gtk_widget_get_style_context(dlg->message_label);
    gtk_style_context_add_class(msg_ctx, "auth-message");
    gtk_box_pack_start(GTK_BOX(text_box), dlg->message_label, FALSE, FALSE, 0);

    if (action_id != NULL && action_id[0] != '\0') {
        gchar *action_str = g_strdup_printf("Action: %s", action_id);
        dlg->action_label = gtk_label_new(action_str);
        g_free(action_str);
        gtk_widget_set_halign(dlg->action_label, GTK_ALIGN_START);
        gtk_label_set_max_width_chars(GTK_LABEL(dlg->action_label), 38);
        gtk_label_set_ellipsize(GTK_LABEL(dlg->action_label), PANGO_ELLIPSIZE_MIDDLE);
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
    g_signal_connect(dlg->entry, "key-press-event", G_CALLBACK(on_window_key_press), dlg);
    gtk_box_pack_start(GTK_BOX(main_box), dlg->entry, FALSE, FALSE, 0);

    /* Info Label */
    dlg->info_label = gtk_label_new("");
    gtk_widget_set_halign(dlg->info_label, GTK_ALIGN_START);
    gtk_label_set_line_wrap(GTK_LABEL(dlg->info_label), TRUE);
    gtk_label_set_max_width_chars(GTK_LABEL(dlg->info_label), 42);
    GtkStyleContext *info_ctx = gtk_widget_get_style_context(dlg->info_label);
    gtk_style_context_add_class(info_ctx, "auth-info");
    gtk_widget_set_no_show_all(dlg->info_label, TRUE);
    gtk_box_pack_start(GTK_BOX(main_box), dlg->info_label, FALSE, FALSE, 0);

    /* Error Label */
    dlg->error_label = gtk_label_new("");
    gtk_widget_set_halign(dlg->error_label, GTK_ALIGN_START);
    gtk_label_set_line_wrap(GTK_LABEL(dlg->error_label), TRUE);
    gtk_label_set_max_width_chars(GTK_LABEL(dlg->error_label), 42);
    GtkStyleContext *err_ctx = gtk_widget_get_style_context(dlg->error_label);
    gtk_style_context_add_class(err_ctx, "auth-error");
    gtk_widget_set_no_show_all(dlg->error_label, TRUE);
    gtk_box_pack_start(GTK_BOX(main_box), dlg->error_label, FALSE, FALSE, 0);

    /* Button Row */
    GtkWidget *btn_box = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 10);
    gtk_widget_set_halign(btn_box, GTK_ALIGN_END);
    gtk_box_pack_start(GTK_BOX(main_box), btn_box, FALSE, FALSE, 2);

    dlg->btn_cancel = gtk_button_new_with_label("Cancel");
    GtkStyleContext *can_ctx = gtk_widget_get_style_context(dlg->btn_cancel);
    gtk_style_context_add_class(can_ctx, "btn-cancel");
    gtk_widget_set_can_focus(dlg->btn_cancel, TRUE);
    g_signal_connect(dlg->btn_cancel, "clicked", G_CALLBACK(on_btn_cancel_clicked), dlg);
    g_signal_connect(dlg->btn_cancel, "key-press-event", G_CALLBACK(on_window_key_press), dlg);
    gtk_box_pack_start(GTK_BOX(btn_box), dlg->btn_cancel, FALSE, FALSE, 0);

    dlg->btn_auth = gtk_button_new_with_label("Authenticate");
    GtkStyleContext *aut_ctx = gtk_widget_get_style_context(dlg->btn_auth);
    gtk_style_context_add_class(aut_ctx, "btn-auth");
    g_signal_connect(dlg->btn_auth, "clicked", G_CALLBACK(on_btn_auth_clicked), dlg);
    g_signal_connect(dlg->btn_auth, "key-press-event", G_CALLBACK(on_window_key_press), dlg);
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

void sys_polkit_dialog_set_info(SysPolkitDialog *dialog, const gchar *info_msg) {
    if (dialog == NULL || dialog->info_label == NULL) return;
    if (info_msg != NULL && info_msg[0] != '\0') {
        gtk_label_set_text(GTK_LABEL(dialog->info_label), info_msg);
        gtk_widget_set_no_show_all(dialog->info_label, FALSE);
        gtk_widget_show(dialog->info_label);
    } else {
        gtk_label_set_text(GTK_LABEL(dialog->info_label), "");
        gtk_widget_hide(dialog->info_label);
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
    /* Cancel button ALWAYS remains active and sensitive so user is NEVER locked out */
    if (dialog->btn_cancel != NULL) {
        gtk_widget_set_sensitive(dialog->btn_cancel, TRUE);
        if (!sensitive) {
            /* If the entry is disabled during PAM verification, ensure keyboard focus is on Cancel */
            gtk_widget_grab_focus(dialog->btn_cancel);
        }
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

GtkWidget *sys_polkit_dialog_get_cancel_button(SysPolkitDialog *dialog) {
    if (dialog == NULL) return NULL;
    return dialog->btn_cancel;
}

void sys_polkit_dialog_destroy(SysPolkitDialog *dialog) {
    if (dialog == NULL) return;
    if (dialog->window != NULL) {
        g_signal_handlers_disconnect_by_data(dialog->window, dialog);
        if (dialog->entry != NULL) {
            g_signal_handlers_disconnect_by_data(dialog->entry, dialog);
        }
        if (dialog->btn_cancel != NULL) {
            g_signal_handlers_disconnect_by_data(dialog->btn_cancel, dialog);
        }
        if (dialog->btn_auth != NULL) {
            g_signal_handlers_disconnect_by_data(dialog->btn_auth, dialog);
        }
        gtk_widget_destroy(dialog->window);
        dialog->window = NULL;
    }
    g_free(dialog);
}

typedef struct {
    GMainLoop *loop;
    SysPolkitDialog *dialog;
    GList *identities;
} WorkerState;

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

static void worker_on_submit(const gchar *password, gpointer user_data) {
    (void)user_data;
    const gchar *pw = password ? password : "";
    gchar *b64 = g_base64_encode((const guchar *)pw, strlen(pw));
    fprintf(stdout, "SUBMIT\t%s\n", b64);
    fflush(stdout);
    explicit_bzero(b64, strlen(b64));
    g_free(b64);
}

static void worker_on_cancel(gpointer user_data) {
    (void)user_data;
    fprintf(stdout, "CANCEL\n");
    fflush(stdout);
}

static void worker_on_identity(PolkitIdentity *identity, gpointer user_data) {
    WorkerState *st = (WorkerState *)user_data;
    gint idx = g_list_index(st->identities, identity);
    if (idx >= 0) {
        fprintf(stdout, "IDENTITY\t%d\n", idx);
        fflush(stdout);
    }
}

static gboolean worker_on_stdin(GIOChannel *src, GIOCondition cond, gpointer user_data) {
    WorkerState *st = (WorkerState *)user_data;
    if (cond & (G_IO_HUP | G_IO_ERR)) {
        if (st->loop && g_main_loop_is_running(st->loop)) {
            g_main_loop_quit(st->loop);
        }
        return G_SOURCE_REMOVE;
    }

    gchar *line = NULL;
    gsize len = 0;
    GError *err = NULL;
    GIOStatus status = g_io_channel_read_line(src, &line, &len, NULL, &err);
    if (status == G_IO_STATUS_AGAIN) {
        g_clear_error(&err);
        return G_SOURCE_CONTINUE;
    }
    if (status != G_IO_STATUS_NORMAL || line == NULL) {
        g_clear_error(&err);
        g_free(line);
        if (st->loop && g_main_loop_is_running(st->loop)) {
            g_main_loop_quit(st->loop);
        }
        return G_SOURCE_REMOVE;
    }

    g_strchomp(line);
    gchar **parts = g_strsplit(line, "\t", -1);
    const gchar *cmd = (parts != NULL && parts[0] != NULL) ? parts[0] : "";

    if (g_strcmp0(cmd, "INIT") == 0 && parts[1] && parts[2] && parts[3] && parts[4] && st->dialog == NULL) {
        gchar *action_id = decode_b64_str(parts[1]);
        gchar *message = decode_b64_str(parts[2]);
        gchar *icon_name = decode_b64_str(parts[3]);
        int n_ids = atoi(parts[4]);

        for (int i = 0; i < n_ids && parts[5 + i] != NULL; i++) {
            gchar *id_str = decode_b64_str(parts[5 + i]);
            GError *id_err = NULL;
            PolkitIdentity *id = polkit_identity_from_string(id_str, &id_err);
            g_clear_error(&id_err);
            if (id != NULL) {
                st->identities = g_list_append(st->identities, id);
            }
            g_free(id_str);
        }

        SysPolkitDialogCallbacks cb = {
            .on_submit = worker_on_submit,
            .on_cancel = worker_on_cancel,
            .on_identity_changed = worker_on_identity,
            .user_data = st
        };
        st->dialog = sys_polkit_dialog_new(action_id, message, icon_name, NULL, st->identities, &cb);
        sys_polkit_dialog_show(st->dialog);

        g_free(action_id);
        g_free(message);
        g_free(icon_name);
    } else if (g_strcmp0(cmd, "INFO") == 0 && st->dialog != NULL) {
        gchar *msg = parts[1] ? decode_b64_str(parts[1]) : g_strdup("");
        sys_polkit_dialog_set_info(st->dialog, msg);
        g_free(msg);
    } else if (g_strcmp0(cmd, "ERROR") == 0 && st->dialog != NULL) {
        gchar *msg = parts[1] ? decode_b64_str(parts[1]) : g_strdup("");
        sys_polkit_dialog_set_error(st->dialog, msg);
        g_free(msg);
    } else if (g_strcmp0(cmd, "PROMPT") == 0 && parts[1] && st->dialog != NULL) {
        gboolean echo_on = (atoi(parts[1]) != 0);
        gchar *prompt = parts[2] ? decode_b64_str(parts[2]) : g_strdup("");
        sys_polkit_dialog_set_prompt(st->dialog, prompt, echo_on);
        g_free(prompt);
    } else if (g_strcmp0(cmd, "SENSITIVE") == 0 && parts[1] && st->dialog != NULL) {
        sys_polkit_dialog_set_sensitive(st->dialog, atoi(parts[1]) != 0);
    } else if (g_strcmp0(cmd, "CLEAR") == 0 && st->dialog != NULL) {
        sys_polkit_dialog_clear_entry(st->dialog);
    } else if (g_strcmp0(cmd, "FOCUS") == 0 && st->dialog != NULL) {
        sys_polkit_dialog_focus_entry(st->dialog);
    } else if (g_strcmp0(cmd, "QUIT") == 0) {
        g_strfreev(parts);
        g_free(line);
        if (st->loop && g_main_loop_is_running(st->loop)) {
            g_main_loop_quit(st->loop);
        }
        return G_SOURCE_REMOVE;
    }

    g_strfreev(parts);
    g_free(line);
    return G_SOURCE_CONTINUE;
}

int sys_polkit_dialog_run_worker(void) {
    if (!gtk_init_check(NULL, NULL)) {
        return 1;
    }

    WorkerState st = {
        .loop = g_main_loop_new(NULL, FALSE),
        .dialog = NULL,
        .identities = NULL
    };

    GIOChannel *in_ch = g_io_channel_unix_new(STDIN_FILENO);
    g_io_channel_set_encoding(in_ch, NULL, NULL);
    g_io_channel_set_flags(in_ch, G_IO_FLAG_NONBLOCK, NULL);
    g_io_add_watch(in_ch, G_IO_IN | G_IO_HUP | G_IO_ERR, worker_on_stdin, &st);

    g_main_loop_run(st.loop);

    if (st.dialog != NULL) {
        sys_polkit_dialog_destroy(st.dialog);
        st.dialog = NULL;
    }
    if (st.identities != NULL) {
        g_list_free_full(st.identities, g_object_unref);
        st.identities = NULL;
    }
    g_io_channel_unref(in_ch);
    g_main_loop_unref(st.loop);
    return 0;
}
