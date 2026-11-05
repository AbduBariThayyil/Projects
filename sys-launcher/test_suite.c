#define SYS_LAUNCHER_TEST 1
#include "sys-launcher.c"
#include <assert.h>

static void test_frecency_io(void) {
    printf("[TEST] Running test_frecency_io...\n");
    char *test_cache = g_build_filename(g_get_tmp_dir(), "sys-launcher-test-cache", NULL);
    g_mkdir_with_parents(test_cache, 0755);
    char *orig_path = frecency_file_path;
    frecency_file_path = g_build_filename(test_cache, "frecency.txt", NULL);
    g_unlink(frecency_file_path);

    /* Initialize fresh map */
    if (frecency_map) g_hash_table_destroy(frecency_map);
    frecency_map = g_hash_table_new_full(g_str_hash, g_str_equal, g_free, NULL);

    /* Record launches */
    record_app_launch("firefox.desktop");
    record_app_launch("firefox.desktop");
    record_app_launch("firefox.desktop");
    record_app_launch("alacritty.desktop");

    /* Verify file exists and has correct contents */
    char *content = NULL;
    gboolean read_ok = g_file_get_contents(frecency_file_path, &content, NULL, NULL);
    assert(read_ok == TRUE);
    assert(content != NULL);
    assert(strstr(content, "firefox.desktop 3") != NULL);
    assert(strstr(content, "alacritty.desktop 1") != NULL);
    g_free(content);

    /* Re-initialize from file to verify loading */
    g_hash_table_destroy(frecency_map);
    frecency_map = g_hash_table_new_full(g_str_hash, g_str_equal, g_free, NULL);

    char *file_data = NULL;
    g_file_get_contents(frecency_file_path, &file_data, NULL, NULL);
    char **lines = g_strsplit(file_data, "\n", -1);
    for (int i = 0; lines[i]; i++) {
        char *line = g_strstrip(lines[i]);
        if (!*line) continue;
        char *space = strchr(line, ' ');
        if (space) {
            *space = '\0';
            char *id = g_strstrip(line);
            char *cnt_str = g_strstrip(space + 1);
            guint count = (guint)g_ascii_strtoull(cnt_str, NULL, 10);
            g_hash_table_insert(frecency_map, g_strdup(id), GUINT_TO_POINTER(count));
        }
    }
    g_strfreev(lines);
    g_free(file_data);

    assert(GPOINTER_TO_UINT(g_hash_table_lookup(frecency_map, "firefox.desktop")) == 3);
    assert(GPOINTER_TO_UINT(g_hash_table_lookup(frecency_map, "alacritty.desktop")) == 1);

    /* Cleanup test file */
    g_unlink(frecency_file_path);
    g_free(frecency_file_path);
    frecency_file_path = orig_path;
    g_rmdir(test_cache);
    g_free(test_cache);

    printf("[TEST] test_frecency_io PASSED.\n");
}

static void test_frecency_bonus_and_scoring(void) {
    printf("[TEST] Running test_frecency_bonus_and_scoring...\n");

    AppItem app_zero = {0};
    app_zero.id = "firefox.desktop";
    app_zero.name = "Firefox";
    app_zero.lower_name = "firefox";
    app_zero.norm_name = "firefox";
    app_zero.launch_count = 0;

    AppItem app_ten = {0};
    app_ten.id = "firefox-dev.desktop";
    app_ten.name = "Firefox Developer Edition";
    app_ten.lower_name = "firefox developer edition";
    app_ten.norm_name = "firefoxdeveloperedition";
    app_ten.launch_count = 10;

    AppItem app_capped = {0};
    app_capped.id = "firefox-nightly.desktop";
    app_capped.name = "Firefox Nightly";
    app_capped.lower_name = "firefox nightly";
    app_capped.norm_name = "firefoxnightly";
    app_capped.launch_count = 50;

    /* Base score with prefix query "fire" */
    gint score_zero = compute_app_score(&app_zero, "fire");
    gint score_ten = compute_app_score(&app_ten, "fire");
    gint score_capped = compute_app_score(&app_capped, "fire");

    assert(score_zero > 0);
    assert(score_ten > 0);
    assert(score_capped > 0);

    /* Verify bonus was applied: count * 150 (capped at 6000) */
    assert(score_ten == score_zero + 1500);
    assert(score_capped == score_zero + 6000);

    printf("[TEST] test_frecency_bonus_and_scoring PASSED.\n");
}

static void test_sorting_empty_query(void) {
    printf("[TEST] Running test_sorting_empty_query...\n");

    AppItem app1 = {0};
    app1.id = "zen.desktop";
    app1.name = "Zen Browser";
    app1.launch_count = 5;

    AppItem app2 = {0};
    app2.id = "alacritty.desktop";
    app2.name = "Alacritty";
    app2.launch_count = 20;

    AppItem app3 = {0};
    app3.id = "brave.desktop";
    app3.name = "Brave Browser";
    app3.launch_count = 20;

    AppItem app4 = {0};
    app4.id = "calc.desktop";
    app4.name = "Calculator";
    app4.launch_count = 0;

    g_free(app_state.current_query);
    app_state.current_query = NULL;
    app_state.is_toggle_mode = FALSE;

    /* Between app2 and app3 (both count 20): alphabetical tie-break puts Alacritty before Brave */
    AppItem *p2 = &app2;
    AppItem *p3 = &app3;
    assert(compare_app_items(&p2, &p3) < 0);
    assert(compare_app_items(&p3, &p2) > 0);

    /* Between app1 (count 5) and app2 (count 20): Alacritty before Zen */
    AppItem *p1 = &app1;
    assert(compare_app_items(&p2, &p1) < 0);
    assert(compare_app_items(&p1, &p2) > 0);

    /* Between app1 (count 5) and app4 (count 0): Zen before Calculator */
    AppItem *p4 = &app4;
    assert(compare_app_items(&p1, &p4) < 0);
    assert(compare_app_items(&p4, &p1) > 0);

    printf("[TEST] test_sorting_empty_query PASSED.\n");
}

static void test_shell_command_execution(void) {
    printf("[TEST] Running test_shell_command_execution...\n");

    const char *marker1 = "/tmp/sys-launcher-test-marker1.tmp";
    const char *marker2 = "/tmp/sys-launcher-test-marker2.tmp";
    g_unlink(marker1);
    g_unlink(marker2);

    /* Test 1: ! prefix */
    g_free(app_state.current_query);
    app_state.current_query = g_strdup_printf("!touch %s", marker1);

    /* Verify filter matches cmd_row and rejects normal apps */
    AppItem dummy_app = {0};
    dummy_app.name = "Dummy";
    assert(app_matches_query(&dummy_app, app_state.current_query) == FALSE);

    /* Mock safe_quit or suppress gtk_main_quit in non-loop context */
    is_quitting = FALSE;
    /* Execute shell command */
    execute_shell_command();
    assert(is_quitting == TRUE);

    /* Wait a moment for async fork/exec */
    g_usleep(150000); /* 150ms */
    assert(g_file_test(marker1, G_FILE_TEST_EXISTS) == TRUE);
    g_unlink(marker1);

    /* Test 2: > prefix */
    g_free(app_state.current_query);
    app_state.current_query = g_strdup_printf(">   touch %s", marker2);
    is_quitting = FALSE;
    execute_shell_command();
    assert(is_quitting == TRUE);

    g_usleep(150000); /* 150ms */
    assert(g_file_test(marker2, G_FILE_TEST_EXISTS) == TRUE);
    g_unlink(marker2);

    g_free(app_state.current_query);
    app_state.current_query = NULL;
    is_quitting = FALSE;
    printf("[TEST] test_shell_command_execution PASSED.\n");
}

static void test_active_monitor_positioning(void) {
    printf("[TEST] Running test_active_monitor_positioning...\n");

    GtkWidget *win = gtk_window_new(GTK_WINDOW_TOPLEVEL);
    gtk_window_set_default_size(GTK_WINDOW(win), 480, 420);
    position_window_on_active_monitor(GTK_WINDOW(win), 480, 420);

    gint win_x = 0, win_y = 0;
    gtk_window_get_position(GTK_WINDOW(win), &win_x, &win_y);

    GdkDisplay *disp = gdk_display_get_default();
    assert(disp != NULL);
    GdkMonitor *mon = gdk_display_get_primary_monitor(disp);
    if (!mon && gdk_display_get_n_monitors(disp) > 0) {
        mon = gdk_display_get_monitor(disp, 0);
    }
    assert(mon != NULL);

    GdkRectangle geo;
    gdk_monitor_get_geometry(mon, &geo);

    gint expected_x = geo.x + (geo.width - 480) / 2;
    gint expected_y = geo.y + (geo.height - 420) / 2;

    printf("  Monitor geo: %dx%d+%d+%d, Window pos: %d,%d, Expected: %d,%d\n",
           geo.width, geo.height, geo.x, geo.y, win_x, win_y, expected_x, expected_y);

    assert(win_x == expected_x);
    assert(win_y == expected_y);

    gtk_widget_destroy(win);
    printf("[TEST] test_active_monitor_positioning PASSED.\n");
}

static gboolean headless_integration_tick(gpointer user_data) {
    (void)user_data;
    printf("  [INTEGRATION] UI initialized successfully in headless X11.\n");
    assert(app_state.window != NULL);
    assert(app_state.entry != NULL);
    assert(app_state.listbox != NULL);
    assert(app_state.cmd_row != NULL);
    assert(app_state.apps != NULL && app_state.apps->len > 0);

    /* Test search entry change to '!' */
    gtk_entry_set_text(GTK_ENTRY(app_state.entry), "!echo hello");
    on_search_changed(GTK_SEARCH_ENTRY(app_state.entry), NULL);
    assert(g_strcmp0(app_state.current_query, "!echo hello") == 0);
    const char *lbl_text = gtk_label_get_text(GTK_LABEL(app_state.cmd_title_label));
    assert(g_strcmp0(lbl_text, "Execute: echo hello") == 0);

    /* Test search entry change back to normal query */
    gtk_entry_set_text(GTK_ENTRY(app_state.entry), "term");
    on_search_changed(GTK_SEARCH_ENTRY(app_state.entry), NULL);
    assert(g_strcmp0(app_state.current_query, "term") == 0);

    printf("  [INTEGRATION] All integration assertions passed. Quitting cleanly.\n");
    safe_quit();
    return G_SOURCE_REMOVE;
}

static void test_headless_integration(void) {
    printf("[TEST] Running test_headless_integration...\n");
    init_frecency();
    build_ui();

    /* Schedule a one-shot timer to verify UI elements and then exit cleanly */
    g_timeout_add(300, headless_integration_tick, NULL);

    gtk_main();

    free_apps();
    free_frecency();
    printf("[TEST] test_headless_integration PASSED.\n");
}

int main(int argc, char **argv) {
    (void)print_usage;
    printf("=========================================\n");
    printf(" Running sys-launcher Test Suite\n");
    printf("=========================================\n");

    gtk_init(&argc, &argv);

    test_frecency_io();
    test_frecency_bonus_and_scoring();
    test_sorting_empty_query();
    test_shell_command_execution();
    test_active_monitor_positioning();
    test_headless_integration();

    printf("=========================================\n");
    printf(" ALL TESTS PASSED SUCCESSFULLY! (6/6)\n");
    printf("=========================================\n");
    return 0;
}
