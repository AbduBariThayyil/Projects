#ifndef SYS_POLKIT_DIALOG_H
#define SYS_POLKIT_DIALOG_H

#include "sys-polkit.h"

typedef struct _SysPolkitDialog SysPolkitDialog;

typedef void (*SysPolkitDialogSubmitCb)(const gchar *password, gpointer user_data);
typedef void (*SysPolkitDialogCancelCb)(gpointer user_data);
typedef void (*SysPolkitDialogIdentityCb)(PolkitIdentity *identity, gpointer user_data);

typedef struct _SysPolkitDialogCallbacks {
    SysPolkitDialogSubmitCb   on_submit;
    SysPolkitDialogCancelCb   on_cancel;
    SysPolkitDialogIdentityCb on_identity_changed;
    gpointer                  user_data;
} SysPolkitDialogCallbacks;

void             sys_polkit_dialog_init_styles(void);

SysPolkitDialog *sys_polkit_dialog_new(const gchar                    *action_id,
                                       const gchar                    *message,
                                       const gchar                    *icon_name,
                                       PolkitDetails                  *details,
                                       GList                          *identities,
                                       const SysPolkitDialogCallbacks *callbacks);

void             sys_polkit_dialog_show(SysPolkitDialog *dialog);
void             sys_polkit_dialog_set_error(SysPolkitDialog *dialog, const gchar *error_msg);
void             sys_polkit_dialog_set_prompt(SysPolkitDialog *dialog, const gchar *prompt, gboolean echo_on);
void             sys_polkit_dialog_set_sensitive(SysPolkitDialog *dialog, gboolean sensitive);
void             sys_polkit_dialog_clear_entry(SysPolkitDialog *dialog);
void             sys_polkit_dialog_focus_entry(SysPolkitDialog *dialog);
PolkitIdentity  *sys_polkit_dialog_get_selected_identity(SysPolkitDialog *dialog);
GtkWidget       *sys_polkit_dialog_get_window(SysPolkitDialog *dialog);
GtkWidget       *sys_polkit_dialog_get_cancel_button(SysPolkitDialog *dialog);
void             sys_polkit_dialog_destroy(SysPolkitDialog *dialog);

#endif /* SYS_POLKIT_DIALOG_H */
