#ifndef SYS_POLKIT_H
#define SYS_POLKIT_H

#ifndef POLKIT_AGENT_I_KNOW_API_IS_SUBJECT_TO_CHANGE
#define POLKIT_AGENT_I_KNOW_API_IS_SUBJECT_TO_CHANGE 1
#endif

#include <glib.h>
#include <gio/gio.h>
#include <gtk/gtk.h>
#include <polkit/polkit.h>
#include <polkitagent/polkitagent.h>

#define SYS_POLKIT_VERSION "1.0.0"
#define SYS_POLKIT_APP_ID  "sys-polkit"
#define SYS_POLKIT_WM_CLASS "sys-polkit"

#endif /* SYS_POLKIT_H */
