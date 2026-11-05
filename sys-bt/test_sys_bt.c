/*
 * test_sys_bt.c: Comprehensive unit and integration tests for sys-bt
 */

#include "sys_bt.h"
#include <assert.h>

static int tests_run = 0;
static int tests_passed = 0;

#define TEST_ASSERT(cond, msg) do { \
    tests_run++; \
    if (cond) { \
        printf("  [PASS] %s\n", msg); \
        tests_passed++; \
    } else { \
        printf("  [FAIL] %s (Line %d)\n", msg, __LINE__); \
    } \
} while(0)

static void test_rfkill_detection(void) {
    printf("[*] Running test_rfkill_detection...\n");
    gboolean blocked = bt_is_rfkill_blocked();
    /* Should return a valid boolean without crashing */
    TEST_ASSERT(blocked == TRUE || blocked == FALSE, "RFKill status returns valid boolean");
}

static void test_system_state_lifecycle(void) {
    printf("[*] Running test_system_state_lifecycle...\n");
    BtSystemState *state = bt_system_state_new();
    TEST_ASSERT(state != NULL, "bt_system_state_new allocates valid state");
    TEST_ASSERT(state->timeout_seconds == SYS_BT_DEFAULT_TIMEOUT, "Default timeout is 300s");
    TEST_ASSERT(state->devices == NULL, "Initial device list is NULL");

    bt_system_state_free(state);
    TEST_ASSERT(TRUE, "bt_system_state_free completes without crash");
}

static void test_dbus_bluez_query(void) {
    printf("[*] Running test_dbus_bluez_query...\n");
    GError *error = NULL;
    GDBusConnection *conn = g_bus_get_sync(G_BUS_TYPE_SYSTEM, NULL, &error);
    TEST_ASSERT(conn != NULL, "Connected to system D-Bus");

    if (conn) {
        BtSystemState *state = bt_system_state_new();
        gboolean ok = bt_query_system_state(conn, state);
        TEST_ASSERT(ok == TRUE, "bt_query_system_state successfully queries BlueZ");
        TEST_ASSERT(state->has_adapter == TRUE, "BlueZ adapter detected (hci0)");
        if (state->has_adapter) {
            TEST_ASSERT(state->adapter.path != NULL, "Adapter path is populated");
            printf("      Detected adapter: %s (%s, Address: %s, Powered: %d)\n",
                   state->adapter.name ? state->adapter.name : "N/A",
                   state->adapter.path,
                   state->adapter.address ? state->adapter.address : "N/A",
                   state->adapter.powered);
        }
        printf("      Found %d devices (%d connected)\n",
               g_list_length(state->devices), state->connected_count);

        bt_system_state_free(state);
        g_object_unref(conn);
    }
}

static void test_state_file_io(void) {
    printf("[*] Running test_state_file_io...\n");
    BtSystemState *state = bt_system_state_new();
    state->has_adapter = TRUE;
    state->adapter.powered = TRUE;
    state->rfkill_blocked = FALSE;
    state->connected_count = 0;
    state->timer_armed = TRUE;
    state->timeout_seconds = 180;
    state->deadline_epoch = (gint64)time(NULL) + 180;

    /* Write state file */
    bt_write_state_file(state);
    char *path = bt_get_state_file_path();
    TEST_ASSERT(g_file_test(path, G_FILE_TEST_EXISTS), "State file written to user runtime dir");

    /* Read back state file */
    BtSystemState *read_state = bt_system_state_new();
    gboolean read_ok = bt_read_state_file(read_state);
    TEST_ASSERT(read_ok == TRUE, "State file read successfully");
    TEST_ASSERT(read_state->timer_armed == TRUE, "State file timer_armed preserved");
    TEST_ASSERT(read_state->timeout_seconds == 180, "State file timeout_seconds preserved");
    TEST_ASSERT(read_state->deadline_epoch == state->deadline_epoch, "State file deadline_epoch matches");
    TEST_ASSERT(read_state->daemon_pid == getpid(), "State file daemon PID matches current process");

    /* Verify countdown remaining calculation */
    int remaining = (int)(read_state->deadline_epoch - (gint64)time(NULL));
    TEST_ASSERT(remaining >= 178 && remaining <= 180, "Idle remaining countdown calculated correctly");

    /* Cleanup */
    bt_remove_state_file();
    TEST_ASSERT(!g_file_test(path, G_FILE_TEST_EXISTS), "State file removed cleanly");
    g_free(path);

    bt_system_state_free(state);
    bt_system_state_free(read_state);
}

static void test_polybar_formatting(void) {
    printf("[*] Running test_polybar_formatting...\n");
    /* cmd_polybar outputs to stdout */
    int ret = cmd_polybar();
    TEST_ASSERT(ret == 0, "cmd_polybar executes cleanly and returns 0");
}

int main(void) {
    printf("========================================\n");
    printf("  sys-bt Test Suite Execution\n");
    printf("========================================\n");

    test_rfkill_detection();
    test_system_state_lifecycle();
    test_dbus_bluez_query();
    test_state_file_io();
    test_polybar_formatting();

    printf("========================================\n");
    printf("  Results: %d/%d tests passed (%s)\n",
           tests_passed, tests_run, tests_passed == tests_run ? "ALL PASSED" : "FAILURES DETECTED");
    printf("========================================\n");

    return (tests_passed == tests_run) ? 0 : 1;
}
