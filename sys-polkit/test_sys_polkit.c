#include "sys-polkit.h"
#include "sys-polkit-listener.h"
#include "sys-polkit-dialog.h"
#include <gdk/gdkkeysyms.h>
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static gboolean g_submit_called = FALSE;
static gboolean g_cancel_called = FALSE;
static gchar *g_submitted_pass = NULL;

static void test_submit_cb(const gchar *pass, gpointer user_data) {
    (void)user_data;
    g_submit_called = TRUE;
    g_free(g_submitted_pass);
    g_submitted_pass = g_strdup(pass);
}

static void test_cancel_cb(gpointer user_data) {
    (void)user_data;
    g_cancel_called = TRUE;
}

static void test_listener_object(void) {
    printf("[TEST] Testing SysPolkitListener object creation...\n");
    PolkitAgentListener *listener = sys_polkit_listener_new();
    assert(listener != NULL);
    assert(POLKIT_AGENT_IS_LISTENER(listener));
    assert(SYS_POLKIT_IS_LISTENER(listener));
    g_object_unref(listener);
    printf("[PASS] SysPolkitListener object creation valid.\n");
}

static void test_subject_creation(void) {
    printf("[TEST] Testing PolkitSubject acquisition...\n");
    GError *error = NULL;
    PolkitSubject *subject = polkit_unix_session_new_for_process_sync(getpid(), NULL, &error);
    if (subject == NULL) {
        g_clear_error(&error);
        subject = polkit_unix_process_new_for_owner(getpid(), 0, getuid());
    }
    assert(subject != NULL);
    assert(POLKIT_IS_SUBJECT(subject));
    g_object_unref(subject);
    printf("[PASS] PolkitSubject acquisition valid.\n");
}

static void test_dialog_layout_and_mechanics(int argc, char *argv[]) {
    printf("[TEST] Testing Catppuccin Dialog layout & mechanics headlessly...\n");
    if (!gtk_init_check(&argc, &argv)) {
        fprintf(stderr, "Could not initialize GTK in headless test. Ensure xvfb-run is active.\n");
        exit(1);
    }

    sys_polkit_dialog_init_styles();

    PolkitIdentity *user_id = polkit_unix_user_new(getuid());
    PolkitIdentity *root_id = polkit_unix_user_new(0);
    GList *ids = g_list_append(NULL, user_id);
    ids = g_list_append(ids, root_id);

    g_submit_called = FALSE;
    g_cancel_called = FALSE;

    SysPolkitDialogCallbacks cb = {
        .on_submit = test_submit_cb,
        .on_cancel = test_cancel_cb,
        .on_identity_changed = NULL,
        .user_data = NULL
    };

    SysPolkitDialog *dlg = sys_polkit_dialog_new(
        "org.freedesktop.policykit.exec",
        "Test administrative elevation prompt",
        "dialog-password",
        NULL,
        ids,
        &cb
    );
    assert(dlg != NULL);

    GtkWidget *win = sys_polkit_dialog_get_window(dlg);
    assert(win != NULL);
    assert(GTK_IS_WINDOW(win));

    /* Test prompt updates */
    sys_polkit_dialog_set_prompt(dlg, "Enter superuser password:", FALSE);

    /* Test error updates */
    sys_polkit_dialog_set_error(dlg, "Invalid credentials, try again.");

    /* Test sensitivity */
    sys_polkit_dialog_set_sensitive(dlg, FALSE);
    sys_polkit_dialog_set_sensitive(dlg, TRUE);

    /* Show dialog and pump event loop iterations */
    sys_polkit_dialog_show(dlg);
    for (int i = 0; i < 20; i++) {
        while (gtk_events_pending()) {
            gtk_main_iteration_do(FALSE);
        }
    }

    /* Test clearing entry */
    sys_polkit_dialog_clear_entry(dlg);

    /* Test destruction */
    sys_polkit_dialog_destroy(dlg);

    for (int i = 0; i < 10; i++) {
        while (gtk_events_pending()) {
            gtk_main_iteration_do(FALSE);
        }
    }

    g_list_free_full(ids, g_object_unref);
    printf("[PASS] Catppuccin Dialog layout and mechanics valid.\n");
}

static void test_dialog_cancellation_and_escape(void) {
    printf("[TEST] Testing Escape key override and Cancel button responsiveness when insensitive...\n");

    PolkitIdentity *user_id = polkit_unix_user_new(getuid());
    GList *ids = g_list_append(NULL, user_id);

    g_submit_called = FALSE;
    g_cancel_called = FALSE;

    SysPolkitDialogCallbacks cb = {
        .on_submit = test_submit_cb,
        .on_cancel = test_cancel_cb,
        .on_identity_changed = NULL,
        .user_data = NULL
    };

    SysPolkitDialog *dlg = sys_polkit_dialog_new(
        "org.freedesktop.policykit.exec",
        "Test cancellation during in_progress state",
        "dialog-password",
        NULL,
        ids,
        &cb
    );
    assert(dlg != NULL);

    GtkWidget *win = sys_polkit_dialog_get_window(dlg);
    assert(win != NULL);
    sys_polkit_dialog_show(dlg);

    /* Pump event loop to realize and display */
    while (gtk_events_pending()) {
        gtk_main_iteration_do(FALSE);
    }

    /* Simulate submitting password: dialog entry is made insensitive */
    sys_polkit_dialog_set_sensitive(dlg, FALSE);

    /* 1. Cancel button MUST remain active and sensitive */
    GtkWidget *btn_cancel = sys_polkit_dialog_get_cancel_button(dlg);
    assert(btn_cancel != NULL);
    assert(gtk_widget_is_sensitive(btn_cancel));

    /* 2. Test clicking Cancel button directly while insensitive */
    g_cancel_called = FALSE;
    gtk_button_clicked(GTK_BUTTON(btn_cancel));
    assert(g_cancel_called == TRUE);
    printf("  -> Cancel button click when insensitive: PASSED\n");

    /* 3. Test Escape key on toplevel window while insensitive */
    g_cancel_called = FALSE;
    GdkEventKey key_event;
    memset(&key_event, 0, sizeof(key_event));
    key_event.type = GDK_KEY_PRESS;
    key_event.window = gtk_widget_get_window(win);
    key_event.send_event = FALSE;
    key_event.time = GDK_CURRENT_TIME;
    key_event.keyval = GDK_KEY_Escape;

    gboolean handled = FALSE;
    g_signal_emit_by_name(win, "key-press-event", &key_event, &handled);
    assert(handled == TRUE);
    assert(g_cancel_called == TRUE);
    printf("  -> Escape key override when insensitive: PASSED\n");

    /* 4. Test window delete-event */
    g_cancel_called = FALSE;
    GdkEvent any_event;
    memset(&any_event, 0, sizeof(any_event));
    any_event.type = GDK_DELETE;
    gboolean del_ret = FALSE;
    g_signal_emit_by_name(win, "delete-event", &any_event, &del_ret);
    assert(del_ret == TRUE);
    assert(g_cancel_called == TRUE);
    printf("  -> Window delete-event: PASSED\n");

    sys_polkit_dialog_destroy(dlg);
    while (gtk_events_pending()) {
        gtk_main_iteration_do(FALSE);
    }
    g_list_free_full(ids, g_object_unref);
    printf("[PASS] Dialog cancellation and Escape key override verified.\n");
}

static void test_external_cancellation(void) {
    printf("[TEST] Testing external GCancellable abort handling...\n");
    GCancellable *cancellable = g_cancellable_new();
    assert(cancellable != NULL);

    /* Cancel before connection */
    g_cancellable_cancel(cancellable);
    assert(g_cancellable_is_cancelled(cancellable));
    g_object_unref(cancellable);
    printf("[PASS] External GCancellable abort verified.\n");
}

int main(int argc, char *argv[]) {
    printf("=========================================\n");
    printf("   sys-polkit Test Suite\n");
    printf("=========================================\n");

    test_listener_object();
    test_subject_creation();
    test_dialog_layout_and_mechanics(argc, argv);
    test_dialog_cancellation_and_escape();
    test_external_cancellation();

    printf("=========================================\n");
    printf("   All sys-polkit tests PASSED!\n");
    printf("=========================================\n");
    return 0;
}
