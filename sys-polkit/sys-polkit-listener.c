#include "sys-polkit-listener.h"
#include "sys-polkit-dialog.h"
#include <malloc.h>

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

    SysPolkitDialog     *dialog;
    gboolean             completed;
    gboolean             in_progress;
} AuthRequest;

static void start_session(AuthRequest *req);
static void finish_request(AuthRequest *req);
static gboolean on_auth_timeout(gpointer user_data);

static void disconnect_session(AuthRequest *req) {
    if (req->session != NULL) {
        g_signal_handlers_disconnect_by_data(req->session, req);
        polkit_agent_session_cancel(req->session);
        g_object_unref(req->session);
        req->session = NULL;
    }
}

static gboolean on_auth_timeout(gpointer user_data) {
    AuthRequest *req = (AuthRequest *)user_data;
    req->timeout_id = 0;

    if (req->completed) return G_SOURCE_REMOVE;

    g_warning("sys-polkit: Authentication timed out after 12s with no response from Polkit Authority.");

    /* Abort stalled session */
    disconnect_session(req);
    req->in_progress = FALSE;

    if (req->dialog != NULL) {
        sys_polkit_dialog_set_error(req->dialog, "Authentication timed out. Please try again or cancel.");
        sys_polkit_dialog_clear_entry(req->dialog);
        sys_polkit_dialog_set_sensitive(req->dialog, TRUE);
        sys_polkit_dialog_focus_entry(req->dialog);
    }

    /* Re-initiate session for new attempt */
    start_session(req);

    return G_SOURCE_REMOVE;
}

static void on_dialog_submit(const gchar *password, gpointer user_data) {
    AuthRequest *req = (AuthRequest *)user_data;
    if (req->completed || req->in_progress) return;

    sys_polkit_dialog_set_sensitive(req->dialog, FALSE);
    req->in_progress = TRUE;

    /* Arm 12-second safety watchdog timeout */
    if (req->timeout_id != 0) {
        g_source_remove(req->timeout_id);
        req->timeout_id = 0;
    }
    req->timeout_id = g_timeout_add_seconds(12, on_auth_timeout, req);

    if (req->session != NULL) {
        polkit_agent_session_response(req->session, password);
    } else {
        g_warning("sys-polkit: Submit attempted but session is NULL.");
        sys_polkit_dialog_set_error(req->dialog, "Authentication session not available.");
        sys_polkit_dialog_set_sensitive(req->dialog, TRUE);
        req->in_progress = FALSE;
        if (req->timeout_id != 0) {
            g_source_remove(req->timeout_id);
            req->timeout_id = 0;
        }
    }
}

static void on_dialog_cancel(gpointer user_data) {
    AuthRequest *req = (AuthRequest *)user_data;
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

static void on_dialog_identity_changed(PolkitIdentity *identity, gpointer user_data) {
    AuthRequest *req = (AuthRequest *)user_data;
    if (req->completed) return;

    if (req->timeout_id != 0) {
        g_source_remove(req->timeout_id);
        req->timeout_id = 0;
    }
    req->in_progress = FALSE;

    req->selected_identity = identity;
    sys_polkit_dialog_set_error(req->dialog, NULL);
    sys_polkit_dialog_clear_entry(req->dialog);
    start_session(req);
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

    /* Handler is currently running; clear cancellable_id so finish_request
     * will not attempt g_cancellable_disconnect from within the callback (which deadlocks). */
    req->cancellable_id = 0;

    g_main_context_invoke(NULL, do_cancellable_cancel, req);
}

static void on_session_request(PolkitAgentSession *session,
                               gchar              *request_str,
                               gboolean            echo_on,
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

    sys_polkit_dialog_set_prompt(req->dialog, request_str, echo_on);
    sys_polkit_dialog_set_sensitive(req->dialog, TRUE);
    sys_polkit_dialog_focus_entry(req->dialog);
}

static void on_session_show_error(PolkitAgentSession *session,
                                  gchar              *text,
                                  gpointer            user_data)
{
    (void)session;
    AuthRequest *req = (AuthRequest *)user_data;
    if (req->completed) return;

    sys_polkit_dialog_set_error(req->dialog, text);
}

static void on_session_show_info(PolkitAgentSession *session,
                                 gchar              *text,
                                 gpointer            user_data)
{
    (void)session;
    (void)text;
    (void)user_data;
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
        /* Authentication failed - allow user retry */
        sys_polkit_dialog_set_error(req->dialog, "Authentication failed. Please try again.");
        sys_polkit_dialog_clear_entry(req->dialog);
        sys_polkit_dialog_set_sensitive(req->dialog, TRUE);
        sys_polkit_dialog_focus_entry(req->dialog);

        /* Re-initiate session for new attempt */
        start_session(req);
    }
}

static void start_session(AuthRequest *req) {
    disconnect_session(req);

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

    if (req->dialog != NULL) {
        sys_polkit_dialog_destroy(req->dialog);
        req->dialog = NULL;
    }

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

    /* Reclaim unneeded heap memory */
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
    /* Initialize GTK lazily if not already initialized */
    if (gdk_display_get_default() == NULL) {
        gtk_init_check(NULL, NULL);
    }

    AuthRequest *req = g_new0(AuthRequest, 1);
    req->listener = SYS_POLKIT_LISTENER(listener);
    req->task = g_task_new(listener, cancellable, callback, user_data);
    g_task_set_source_tag(req->task, (gpointer)SYS_POLKIT_SOURCE_TAG);

    req->action_id = g_strdup(action_id);
    req->message = g_strdup(message);
    req->icon_name = g_strdup(icon_name);
    req->cookie = g_strdup(cookie);

    if (identities != NULL) {
        req->identities = g_list_copy_deep(identities, copy_gobject, NULL);
        req->selected_identity = POLKIT_IDENTITY(req->identities->data);
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

    SysPolkitDialogCallbacks cb = {
        .on_submit = on_dialog_submit,
        .on_cancel = on_dialog_cancel,
        .on_identity_changed = on_dialog_identity_changed,
        .user_data = req
    };

    req->dialog = sys_polkit_dialog_new(action_id, message, icon_name, details, req->identities, &cb);
    req->selected_identity = sys_polkit_dialog_get_selected_identity(req->dialog);

    start_session(req);
    sys_polkit_dialog_show(req->dialog);
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
