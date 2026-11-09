#include "emulator.h"
#include "audio.h"
#include "discovery.h"
#include "hud.h"
#include "config.h"
#include "browser.h"
#include "../../core/link_protocol.h"

#include <SDL2/SDL.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <signal.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <netinet/tcp.h>
#include <arpa/inet.h>
#include <fcntl.h>
#include <sys/time.h>

#include <mgba/internal/gba/input.h>

static const char* DEFAULT_GBA_DIR = "/home/vibecoder/Games/Console Games/GBA";

static volatile bool g_running = true;

static void sigint_handler(int sig) {
    (void)sig;
    g_running = false;
}

static uint64_t get_time_us(void) {
    struct timeval tv;
    gettimeofday(&tv, NULL);
    return (uint64_t)(tv.tv_sec * 1000000 + tv.tv_usec);
}

int main(int argc, char** argv) {
    char picked_rom[1024] = {0};
    char* dynamic_rom = NULL;
    const char* rom_path = NULL;

    /* Load user configuration from ~/.config/gba-crossplay/config.ini */
    GBAConfig config;
    gba_config_load_file(&config, gba_config_get_default_path());

    bool headless = false;
    bool is_multiplayer = false;
    bool is_host = false;
    char remote_ip[64] = "127.0.0.1";
    uint16_t port = GBA_LINK_DEFAULT_PORT;
    uint8_t turbo_mult = config.turbo_multiplier;

    /* Parse CLI options first */
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--headless") == 0) {
            headless = true;
        } else if (strcmp(argv[i], "--host") == 0) {
            is_multiplayer = true;
            is_host = true;
            if (i + 1 < argc && argv[i + 1][0] != '-') {
                port = (uint16_t)atoi(argv[++i]);
            }
        } else if (strcmp(argv[i], "--join") == 0) {
            is_multiplayer = true;
            is_host = false;
            if (i + 1 < argc && argv[i + 1][0] != '-') {
                strncpy(remote_ip, argv[++i], sizeof(remote_ip) - 1);
            }
            if (i + 1 < argc && argv[i + 1][0] != '-') {
                port = (uint16_t)atoi(argv[++i]);
            }
        } else if (strcmp(argv[i], "--turbo") == 0 && i + 1 < argc) {
            turbo_mult = (uint8_t)atoi(argv[++i]);
        } else if (argv[i][0] != '-' && !rom_path) {
            rom_path = argv[i];
        }
    }

    signal(SIGINT, sigint_handler);

    /* Initialize SDL early for Window & Renderer */
    SDL_Window* window = NULL;
    SDL_Renderer* renderer = NULL;
    SDL_Texture* texture = NULL;
    SDL_GameController* controller = NULL;

    if (!headless) {
        if (SDL_Init(SDL_INIT_VIDEO | SDL_INIT_AUDIO | SDL_INIT_GAMECONTROLLER) < 0) {
            fprintf(stderr, "SDL Init failed: %s\n", SDL_GetError());
            return 1;
        }

        /* Use nearest-neighbor scaling for tack-sharp GBA pixel art */
        SDL_SetHint(SDL_HINT_RENDER_SCALE_QUALITY, "0");

        window = SDL_CreateWindow("GBA Crossplay [Arch Linux]",
                                  SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED,
                                  720, 480, SDL_WINDOW_RESIZABLE);
        if (!window) {
            fprintf(stderr, "Window creation failed: %s\n", SDL_GetError());
            return 1;
        }

        renderer = SDL_CreateRenderer(window, -1, SDL_RENDERER_ACCELERATED);
        if (!renderer) {
            renderer = SDL_CreateRenderer(window, -1, SDL_RENDERER_SOFTWARE);
        }

        /* Open first available gamepad */
        for (int i = 0; i < SDL_NumJoysticks(); i++) {
            if (SDL_IsGameController(i)) {
                controller = SDL_GameControllerOpen(i);
                if (controller) {
                    printf("[GBA-Crossplay] Gamepad connected: %s\n", SDL_GameControllerName(controller));
                    break;
                }
            }
        }
    }

    /* If no ROM path provided, open interactive Game Browser or File Picker */
    if (!rom_path) {
        if (!headless && renderer) {
            GBABrowser browser;
            if (gba_browser_scan(&browser, DEFAULT_GBA_DIR, renderer)) {
                dynamic_rom = gba_browser_run(&browser, window, renderer);
                gba_browser_free(&browser);
                if (!dynamic_rom) {
                    /* User exited browser with Escape */
                    if (controller) SDL_GameControllerClose(controller);
                    if (renderer) SDL_DestroyRenderer(renderer);
                    if (window) SDL_DestroyWindow(window);
                    SDL_Quit();
                    return 0;
                }
                rom_path = dynamic_rom;
            }
        }

        /* Fallback if browser didn't return a path */
        if (!rom_path) {
            char cmd[1024];
            snprintf(cmd, sizeof(cmd),
                     "GTK_THEME=catppuccin-mocha-teal-standard+default ADW_DEBUG_COLOR_SCHEME=prefer-dark zenity --file-selection --filename='%s/' --title='Select GBA ROM' --file-filter='GBA ROMs (*.gba *.bin)|*.gba *.bin' --file-filter='All Files|*' 2>/dev/null",
                     DEFAULT_GBA_DIR);

            FILE* fp = popen(cmd, "r");
            if (fp) {
                if (fgets(picked_rom, sizeof(picked_rom), fp)) {
                    size_t len = strlen(picked_rom);
                    if (len > 0 && picked_rom[len - 1] == '\n') {
                        picked_rom[len - 1] = '\0';
                    }
                }
                pclose(fp);
            }

            if (picked_rom[0] != '\0') {
                rom_path = picked_rom;
            } else {
                printf("No ROM selected. Exiting.\n");
                if (!headless) {
                    if (controller) SDL_GameControllerClose(controller);
                    if (renderer) SDL_DestroyRenderer(renderer);
                    if (window) SDL_DestroyWindow(window);
                    SDL_Quit();
                }
                return 0;
            }
        }
    }

    /* Initial Socket Setup (if CLI specified --host or --join) */
    int socket_fd = -1;
    int listen_fd = -1;
    uint8_t player_id = is_host ? 0 : 1;

    if (is_multiplayer) {
        if (is_host) {
            listen_fd = socket(AF_INET, SOCK_STREAM, 0);
            if (listen_fd >= 0) {
                int reuse = 1;
                setsockopt(listen_fd, SOL_SOCKET, SO_REUSEADDR, &reuse, sizeof(reuse));

                struct sockaddr_in addr;
                memset(&addr, 0, sizeof(addr));
                addr.sin_family = AF_INET;
                addr.sin_port = htons(port);
                addr.sin_addr.s_addr = htonl(INADDR_ANY);

                if (bind(listen_fd, (struct sockaddr*)&addr, sizeof(addr)) == 0) {
                    listen(listen_fd, 1);
                    int flags = fcntl(listen_fd, F_GETFL, 0);
                    fcntl(listen_fd, F_SETFL, flags | O_NONBLOCK);
                    printf("[GBA-Crossplay] Hosting on port %d... Beacon active.\n", port);
                    gba_discovery_start_beacon("GBA Game", port);
                }
            }
        } else {
            printf("[GBA-Crossplay] Connecting to %s:%d...\n", remote_ip, port);
            socket_fd = socket(AF_INET, SOCK_STREAM, 0);
            if (socket_fd >= 0) {
                int one = 1;
                setsockopt(socket_fd, IPPROTO_TCP, TCP_NODELAY, (char*)&one, sizeof(one));

                struct sockaddr_in addr;
                memset(&addr, 0, sizeof(addr));
                addr.sin_family = AF_INET;
                addr.sin_port = htons(port);
                inet_pton(AF_INET, remote_ip, &addr.sin_addr);

                if (connect(socket_fd, (struct sockaddr*)&addr, sizeof(addr)) == 0) {
                    printf("[GBA-Crossplay] Connected to host successfully!\n");
                } else {
                    printf("[GBA-Crossplay] Host unreachable, continuing in single-player...\n");
                    close(socket_fd);
                    socket_fd = -1;
                    is_multiplayer = false;
                }
            }
        }
    }

    /* Initialize Emulator Texture & Audio */
    if (!headless) {
        texture = SDL_CreateTexture(renderer, SDL_PIXELFORMAT_ABGR8888,
                                    SDL_TEXTUREACCESS_STREAMING,
                                    GBA_VIDEO_WIDTH, GBA_VIDEO_HEIGHT);
        gba_audio_init(44100, 2);
    }

    /* Initialize Emulator Core */
    GBAEmulator* emu = gba_emulator_create(rom_path, player_id, socket_fd);
    if (!emu) {
        fprintf(stderr, "Failed to initialize GBA core for %s.\n", rom_path);
        if (dynamic_rom) free(dynamic_rom);
        if (!headless) {
            if (texture) SDL_DestroyTexture(texture);
            if (renderer) SDL_DestroyRenderer(renderer);
            if (window) SDL_DestroyWindow(window);
            SDL_Quit();
        }
        return 1;
    }

    GBATurboCoordinator* turbo = gba_emulator_get_turbo(emu);
    if (turbo && turbo_mult > 1) {
        turbo->multiplier = turbo_mult;
    }

    GBAHUDState hud;
    gba_hud_init(&hud);

    if (is_multiplayer) {
        if (is_host) {
            hud.net_mode = GBA_NET_HOSTING;
            hud.connected = false;
        } else {
            hud.net_mode = (socket_fd >= 0) ? GBA_NET_CONNECTED : GBA_NET_SINGLE_PLAYER;
            hud.connected = (socket_fd >= 0);
        }
    } else {
        hud.net_mode = GBA_NET_SINGLE_PLAYER;
        hud.connected = false;
    }

    hud.player_id = player_id;
    hud.total_players = 2;
    snprintf(hud.remote_ip, sizeof(hud.remote_ip), "%s", remote_ip);
    hud.turbo_multiplier = turbo_mult;

    uint32_t keys = 0;
    bool turbo_hold = false;
    bool turbo_toggle = false;
    bool spam_a_active = false;
    bool spam_b_active = false;

    uint64_t last_frame_time = get_time_us();
    uint64_t fps_timer = last_frame_time;
    int frame_count = 0;

    printf("[GBA-Crossplay] Running game: %s (Mode: %s)\n",
           gba_emulator_get_title(emu),
           (hud.net_mode == GBA_NET_SINGLE_PLAYER) ? "Single Player" : "Multiplayer");

    while (g_running) {
        /* Check incoming connection for host (supports Midgame Connection like MyBoy!) */
        if (hud.net_mode == GBA_NET_HOSTING && socket_fd < 0 && listen_fd >= 0) {
            struct sockaddr_in client_addr;
            socklen_t client_len = sizeof(client_addr);
            int new_fd = accept(listen_fd, (struct sockaddr*)&client_addr, &client_len);
            if (new_fd >= 0) {
                socket_fd = new_fd;
                int one = 1;
                setsockopt(socket_fd, IPPROTO_TCP, TCP_NODELAY, (char*)&one, sizeof(one));

                char client_ip[64];
                inet_ntop(AF_INET, &client_addr.sin_addr, client_ip, sizeof(client_ip));
                printf("[GBA-Crossplay] Midgame peer connected from %s!\n", client_ip);
                snprintf(hud.remote_ip, sizeof(hud.remote_ip), "%s", client_ip);
                hud.net_mode = GBA_NET_CONNECTED;
                hud.connected = true;
                gba_emulator_set_network(emu, socket_fd, 0);
                gba_hud_show_toast(&hud, "[PEER CONNECTED - LINK ACTIVE!]", (SDL_Color){ 166, 227, 161, 255 }, 2500);
            }
        }

        if (!headless) {
            SDL_Event ev;
            while (SDL_PollEvent(&ev)) {
                if (ev.type == SDL_QUIT) {
                    g_running = false;
                }

                /* ========================================================
                 *  MENU NAVIGATION (When Pause Menu is Active)
                 * ======================================================== */
                else if (hud.menu_open) {
                    if (ev.type == SDL_KEYDOWN) {
                        SDL_Keycode k = ev.key.keysym.sym;
                        if (k == SDLK_ESCAPE) {
                            hud.menu_open = false;
                        } else if (k == SDLK_UP) {
                            hud.menu_selected = (hud.menu_selected - 1 + MENU_COUNT) % MENU_COUNT;
                        } else if (k == SDLK_DOWN) {
                            hud.menu_selected = (hud.menu_selected + 1) % MENU_COUNT;
                        } else if (k == SDLK_LEFT) {
                            if (hud.menu_selected == MENU_SAVE_STATE || hud.menu_selected == MENU_LOAD_STATE) {
                                hud.selected_slot = (hud.selected_slot > 1) ? hud.selected_slot - 1 : 9;
                            } else if (hud.menu_selected == MENU_MULTIPLAYER && hud.net_mode == GBA_NET_SINGLE_PLAYER) {
                                hud.mp_action_mode = (hud.mp_action_mode == 0) ? 1 : 0;
                            } else if (hud.menu_selected == MENU_TURBO_SPEED) {
                                hud.turbo_multiplier = (hud.turbo_multiplier <= 2) ? 4 : hud.turbo_multiplier - 1;
                                if (turbo) turbo->multiplier = hud.turbo_multiplier;
                            }
                        } else if (k == SDLK_RIGHT) {
                            if (hud.menu_selected == MENU_SAVE_STATE || hud.menu_selected == MENU_LOAD_STATE) {
                                hud.selected_slot = (hud.selected_slot < 9) ? hud.selected_slot + 1 : 1;
                            } else if (hud.menu_selected == MENU_MULTIPLAYER && hud.net_mode == GBA_NET_SINGLE_PLAYER) {
                                hud.mp_action_mode = (hud.mp_action_mode == 0) ? 1 : 0;
                            } else if (hud.menu_selected == MENU_TURBO_SPEED) {
                                hud.turbo_multiplier = (hud.turbo_multiplier >= 4) ? 2 : hud.turbo_multiplier + 1;
                                if (turbo) turbo->multiplier = hud.turbo_multiplier;
                            }
                        } else if (k == SDLK_RETURN || k == SDLK_SPACE) {
                            if (hud.menu_selected == MENU_RESUME) {
                                hud.menu_open = false;
                            } else if (hud.menu_selected == MENU_SAVE_STATE) {
                                bool ok = gba_emulator_save_state(emu, hud.selected_slot);
                                char msg[64];
                                snprintf(msg, sizeof(msg), ok ? "[SAVED STATE SLOT %d]" : "[SAVE FAILED SLOT %d]", hud.selected_slot);
                                gba_hud_show_toast(&hud, msg, ok ? (SDL_Color){166,227,161,255} : (SDL_Color){243,139,168,255}, 2000);
                                hud.menu_open = false;
                            } else if (hud.menu_selected == MENU_LOAD_STATE) {
                                bool ok = gba_emulator_load_state(emu, hud.selected_slot);
                                char msg[64];
                                snprintf(msg, sizeof(msg), ok ? "[LOADED STATE SLOT %d]" : "[SLOT %d EMPTY]", hud.selected_slot);
                                gba_hud_show_toast(&hud, msg, ok ? (SDL_Color){148,226,213,255} : (SDL_Color){243,139,168,255}, 2000);
                                hud.menu_open = false;
                            } else if (hud.menu_selected == MENU_MULTIPLAYER) {
                                if (hud.net_mode == GBA_NET_SINGLE_PLAYER) {
                                    if (hud.mp_action_mode == 0) {
                                        /* MIDGAME HOST: Start listening on port 8765 */
                                        listen_fd = socket(AF_INET, SOCK_STREAM, 0);
                                        if (listen_fd >= 0) {
                                            int reuse = 1;
                                            setsockopt(listen_fd, SOL_SOCKET, SO_REUSEADDR, &reuse, sizeof(reuse));
                                            struct sockaddr_in addr;
                                            memset(&addr, 0, sizeof(addr));
                                            addr.sin_family = AF_INET;
                                            addr.sin_port = htons(port);
                                            addr.sin_addr.s_addr = htonl(INADDR_ANY);
                                            if (bind(listen_fd, (struct sockaddr*)&addr, sizeof(addr)) == 0) {
                                                listen(listen_fd, 1);
                                                int flags = fcntl(listen_fd, F_GETFL, 0);
                                                fcntl(listen_fd, F_SETFL, flags | O_NONBLOCK);
                                                gba_discovery_start_beacon(gba_emulator_get_title(emu), port);
                                                hud.net_mode = GBA_NET_HOSTING;
                                                hud.player_id = 0;
                                                gba_emulator_set_network(emu, -1, 0);
                                                gba_hud_show_toast(&hud, "[HOSTING ACTIVE - READY FOR PEER]", (SDL_Color){249, 226, 175, 255}, 2500);
                                            }
                                        }
                                        hud.menu_open = false;
                                    } else {
                                        /* MIDGAME JOIN: Connect to Remote IP */
                                        char target_ip[64] = "192.168.1.";
                                        FILE* p = popen("GTK_THEME=catppuccin-mocha-teal-standard+default ADW_DEBUG_COLOR_SCHEME=prefer-dark zenity --entry --title='Join Multiplayer' --text='Enter Host IP Address:' --entry-text='192.168.1.' 2>/dev/null", "r");
                                        if (p) {
                                            if (fgets(target_ip, sizeof(target_ip), p)) {
                                                size_t len = strlen(target_ip);
                                                if (len > 0 && target_ip[len - 1] == '\n') target_ip[len - 1] = '\0';
                                            }
                                            pclose(p);
                                        }
                                        if (target_ip[0] != '\0' && strcmp(target_ip, "192.168.1.") != 0) {
                                            int sfd = socket(AF_INET, SOCK_STREAM, 0);
                                            if (sfd >= 0) {
                                                int one = 1;
                                                setsockopt(sfd, IPPROTO_TCP, TCP_NODELAY, (char*)&one, sizeof(one));

                                                struct sockaddr_in saddr;
                                                memset(&saddr, 0, sizeof(saddr));
                                                saddr.sin_family = AF_INET;
                                                saddr.sin_port = htons(port);
                                                inet_pton(AF_INET, target_ip, &saddr.sin_addr);
                                                if (connect(sfd, (struct sockaddr*)&saddr, sizeof(saddr)) == 0) {
                                                    socket_fd = sfd;
                                                    hud.net_mode = GBA_NET_CONNECTED;
                                                    hud.connected = true;
                                                    hud.player_id = 1;
                                                    snprintf(hud.remote_ip, sizeof(hud.remote_ip), "%s", target_ip);
                                                    gba_emulator_set_network(emu, socket_fd, 1);
                                                    gba_hud_show_toast(&hud, "[CONNECTED TO HOST - LINK ACTIVE!]", (SDL_Color){166, 227, 161, 255}, 2500);
                                                } else {
                                                    close(sfd);
                                                    gba_hud_show_toast(&hud, "[FAILED TO CONNECT]", (SDL_Color){243, 139, 168, 255}, 2500);
                                                }
                                            }
                                        }
                                        hud.menu_open = false;
                                    }
                                } else {
                                    /* MIDGAME DISCONNECT */
                                    gba_discovery_stop_beacon();
                                    if (listen_fd >= 0) { close(listen_fd); listen_fd = -1; }
                                    if (socket_fd >= 0) { close(socket_fd); socket_fd = -1; }
                                    gba_emulator_disconnect_network(emu);
                                    hud.net_mode = GBA_NET_SINGLE_PLAYER;
                                    hud.connected = false;
                                    hud.player_id = 0;
                                    gba_hud_show_toast(&hud, "[RETURNED TO SINGLE PLAYER]", (SDL_Color){137, 180, 250, 255}, 2500);
                                    hud.menu_open = false;
                                }
                            } else if (hud.menu_selected == MENU_TURBO_SPEED) {
                                hud.turbo_multiplier = (hud.turbo_multiplier >= 4) ? 2 : hud.turbo_multiplier + 1;
                                if (turbo) turbo->multiplier = hud.turbo_multiplier;
                            } else if (hud.menu_selected == MENU_TOGGLE_HUD) {
                                hud.show_hud = !hud.show_hud;
                            } else if (hud.menu_selected == MENU_QUIT) {
                                g_running = false;
                            }
                        }
                    } else if (ev.type == SDL_CONTROLLERBUTTONDOWN) {
                        SDL_GameControllerButton b = ev.cbutton.button;
                        if (b == SDL_CONTROLLER_BUTTON_B || b == SDL_CONTROLLER_BUTTON_START) {
                            hud.menu_open = false;
                        } else if (b == SDL_CONTROLLER_BUTTON_DPAD_UP) {
                            hud.menu_selected = (hud.menu_selected - 1 + MENU_COUNT) % MENU_COUNT;
                        } else if (b == SDL_CONTROLLER_BUTTON_DPAD_DOWN) {
                            hud.menu_selected = (hud.menu_selected + 1) % MENU_COUNT;
                        } else if (b == SDL_CONTROLLER_BUTTON_DPAD_LEFT) {
                            if (hud.menu_selected == MENU_SAVE_STATE || hud.menu_selected == MENU_LOAD_STATE) {
                                hud.selected_slot = (hud.selected_slot > 1) ? hud.selected_slot - 1 : 9;
                            }
                        } else if (b == SDL_CONTROLLER_BUTTON_DPAD_RIGHT) {
                            if (hud.menu_selected == MENU_SAVE_STATE || hud.menu_selected == MENU_LOAD_STATE) {
                                hud.selected_slot = (hud.selected_slot < 9) ? hud.selected_slot + 1 : 1;
                            }
                        } else if (b == SDL_CONTROLLER_BUTTON_A) {
                            if (hud.menu_selected == MENU_RESUME) {
                                hud.menu_open = false;
                            } else if (hud.menu_selected == MENU_SAVE_STATE) {
                                bool ok = gba_emulator_save_state(emu, hud.selected_slot);
                                char msg[64];
                                snprintf(msg, sizeof(msg), ok ? "[SAVED STATE SLOT %d]" : "[SAVE FAILED SLOT %d]", hud.selected_slot);
                                gba_hud_show_toast(&hud, msg, ok ? (SDL_Color){166,227,161,255} : (SDL_Color){243,139,168,255}, 2000);
                                hud.menu_open = false;
                            } else if (hud.menu_selected == MENU_LOAD_STATE) {
                                bool ok = gba_emulator_load_state(emu, hud.selected_slot);
                                char msg[64];
                                snprintf(msg, sizeof(msg), ok ? "[LOADED STATE SLOT %d]" : "[SLOT %d EMPTY]", hud.selected_slot);
                                gba_hud_show_toast(&hud, msg, ok ? (SDL_Color){148,226,213,255} : (SDL_Color){243,139,168,255}, 2000);
                                hud.menu_open = false;
                            } else if (hud.menu_selected == MENU_QUIT) {
                                g_running = false;
                            }
                        }
                    }
                }

                /* ========================================================
                 *  GAMEPLAY CONTROLS & DIRECT SHORTCUTS
                 * ======================================================== */
                else if (ev.type == SDL_KEYDOWN || ev.type == SDL_KEYUP) {
                    bool down = (ev.type == SDL_KEYDOWN);
                    SDL_Keycode k = ev.key.keysym.sym;

                    /* 1-9: Instant Save States */
                    if (down && k >= SDLK_1 && k <= SDLK_9) {
                        int slot = k - SDLK_1 + 1;
                        bool ok = gba_emulator_save_state(emu, slot);
                        char msg[64];
                        if (ok) {
                            snprintf(msg, sizeof(msg), "[SAVED STATE SLOT %d]", slot);
                            gba_hud_show_toast(&hud, msg, (SDL_Color){ 166, 227, 161, 255 }, 2000);
                        } else {
                            snprintf(msg, sizeof(msg), "[SAVE FAILED SLOT %d]", slot);
                            gba_hud_show_toast(&hud, msg, (SDL_Color){ 243, 139, 168, 255 }, 2000);
                        }
                    }
                    /* F1-F9: Instant Load States */
                    else if (down && k >= SDLK_F1 && k <= SDLK_F9) {
                        int slot = k - SDLK_F1 + 1;
                        bool ok = gba_emulator_load_state(emu, slot);
                        char msg[64];
                        if (ok) {
                            snprintf(msg, sizeof(msg), "[LOADED STATE SLOT %d]", slot);
                            gba_hud_show_toast(&hud, msg, (SDL_Color){ 148, 226, 213, 255 }, 2000);
                        } else {
                            snprintf(msg, sizeof(msg), "[SLOT %d EMPTY]", slot);
                            gba_hud_show_toast(&hud, msg, (SDL_Color){ 243, 139, 168, 255 }, 2000);
                        }
                    }
                    /* Standard Controls */
                    else if (k == config.key_a) { down ? (keys |= (1 << GBA_KEY_A)) : (keys &= ~(1 << GBA_KEY_A)); }
                    else if (k == config.key_b) { down ? (keys |= (1 << GBA_KEY_B)) : (keys &= ~(1 << GBA_KEY_B)); }
                    else if (k == config.key_l) { down ? (keys |= (1 << GBA_KEY_L)) : (keys &= ~(1 << GBA_KEY_L)); }
                    else if (k == config.key_r) { down ? (keys |= (1 << GBA_KEY_R)) : (keys &= ~(1 << GBA_KEY_R)); }
                    else if (k == config.key_start) { down ? (keys |= (1 << GBA_KEY_START)) : (keys &= ~(1 << GBA_KEY_START)); }
                    else if (k == config.key_select) { down ? (keys |= (1 << GBA_KEY_SELECT)) : (keys &= ~(1 << GBA_KEY_SELECT)); }
                    else if (k == config.key_up) { down ? (keys |= (1 << GBA_KEY_UP)) : (keys &= ~(1 << GBA_KEY_UP)); }
                    else if (k == config.key_down) { down ? (keys |= (1 << GBA_KEY_DOWN)) : (keys &= ~(1 << GBA_KEY_DOWN)); }
                    else if (k == config.key_left) { down ? (keys |= (1 << GBA_KEY_LEFT)) : (keys &= ~(1 << GBA_KEY_LEFT)); }
                    else if (k == config.key_right) { down ? (keys |= (1 << GBA_KEY_RIGHT)) : (keys &= ~(1 << GBA_KEY_RIGHT)); }
                    else if (k == config.key_turbo_hold) {
                        turbo_hold = down;
                        gba_turbo_set_local(turbo, turbo_hold || turbo_toggle);
                    } else if (k == config.key_turbo_toggle && down) {
                        turbo_toggle = !turbo_toggle;
                        hud.turbo_is_toggle = turbo_toggle;
                        gba_turbo_set_local(turbo, turbo_hold || turbo_toggle);
                    } else if (k == config.key_spam_a) {
                        spam_a_active = down;
                    } else if (k == config.key_spam_b) {
                        spam_b_active = down;
                    } else if (k == config.key_hud && down) {
                        hud.show_hud = !hud.show_hud;
                    } else if (k == SDLK_ESCAPE && down) {
                        hud.menu_open = true;
                        hud.menu_selected = MENU_RESUME;
                    }
                } else if (ev.type == SDL_CONTROLLERBUTTONDOWN || ev.type == SDL_CONTROLLERBUTTONUP) {
                    bool down = (ev.type == SDL_CONTROLLERBUTTONDOWN);
                    SDL_GameControllerButton b = ev.cbutton.button;

                    if (b == config.pad_a) { down ? (keys |= (1 << GBA_KEY_A)) : (keys &= ~(1 << GBA_KEY_A)); }
                    else if (b == config.pad_b) { down ? (keys |= (1 << GBA_KEY_B)) : (keys &= ~(1 << GBA_KEY_B)); }
                    else if (b == config.pad_l) { down ? (keys |= (1 << GBA_KEY_L)) : (keys &= ~(1 << GBA_KEY_L)); }
                    else if (b == config.pad_r) { down ? (keys |= (1 << GBA_KEY_R)) : (keys &= ~(1 << GBA_KEY_R)); }
                    else if (b == config.pad_start) { down ? (keys |= (1 << GBA_KEY_START)) : (keys &= ~(1 << GBA_KEY_START)); }
                    else if (b == config.pad_select) { down ? (keys |= (1 << GBA_KEY_SELECT)) : (keys &= ~(1 << GBA_KEY_SELECT)); }
                    else if (b == SDL_CONTROLLER_BUTTON_DPAD_UP) { down ? (keys |= (1 << GBA_KEY_UP)) : (keys &= ~(1 << GBA_KEY_UP)); }
                    else if (b == SDL_CONTROLLER_BUTTON_DPAD_DOWN) { down ? (keys |= (1 << GBA_KEY_DOWN)) : (keys &= ~(1 << GBA_KEY_DOWN)); }
                    else if (b == SDL_CONTROLLER_BUTTON_DPAD_LEFT) { down ? (keys |= (1 << GBA_KEY_LEFT)) : (keys &= ~(1 << GBA_KEY_LEFT)); }
                    else if (b == SDL_CONTROLLER_BUTTON_DPAD_RIGHT) { down ? (keys |= (1 << GBA_KEY_RIGHT)) : (keys &= ~(1 << GBA_KEY_RIGHT)); }
                    else if (b == config.pad_turbo_hold) {
                        turbo_hold = down;
                        gba_turbo_set_local(turbo, turbo_hold || turbo_toggle);
                    } else if (b == config.pad_turbo_toggle && down) {
                        turbo_toggle = !turbo_toggle;
                        hud.turbo_is_toggle = turbo_toggle;
                        gba_turbo_set_local(turbo, turbo_hold || turbo_toggle);
                    } else if (b == config.pad_spam_a) {
                        spam_a_active = down;
                    } else if (b == config.pad_spam_b) {
                        spam_b_active = down;
                    } else if (b == SDL_CONTROLLER_BUTTON_BACK && down) {
                        hud.menu_open = true;
                        hud.menu_selected = MENU_RESUME;
                    }
                }
            }
        }

        /* If Menu is Open: Pause Emulation and only Render Menu Frame */
        if (hud.menu_open) {
            if (!headless && renderer && texture) {
                int win_w, win_h;
                SDL_GetWindowSize(window, &win_w, &win_h);

                SDL_SetRenderDrawColor(renderer, 10, 10, 12, 255);
                SDL_RenderClear(renderer);

                int scale_x = win_w / GBA_VIDEO_WIDTH;
                int scale_y = win_h / GBA_VIDEO_HEIGHT;
                int scale = (scale_x < scale_y) ? scale_x : scale_y;
                if (scale < 1) scale = 1;

                int dst_w = GBA_VIDEO_WIDTH * scale;
                int dst_h = GBA_VIDEO_HEIGHT * scale;
                SDL_Rect dst_rect = { (win_w - dst_w) / 2, (win_h - dst_h) / 2, dst_w, dst_h };

                SDL_RenderCopy(renderer, texture, NULL, &dst_rect);
                gba_hud_draw(renderer, win_w, win_h, &hud);
                SDL_RenderPresent(renderer);
            }
            usleep(16000);
            continue;
        }

        /* Apply Auto-fire / Spam A & B alternating every 2 frames */
        uint32_t active_keys = keys;
        if (spam_a_active) {
            if ((frame_count % 4) < 2) {
                active_keys |= (1 << GBA_KEY_A);
            } else {
                active_keys &= ~(1 << GBA_KEY_A);
            }
        }
        if (spam_b_active) {
            if ((frame_count % 4) < 2) {
                active_keys |= (1 << GBA_KEY_B);
            } else {
                active_keys &= ~(1 << GBA_KEY_B);
            }
        }

        gba_emulator_set_keys(emu, active_keys);
        gba_emulator_step_frame(emu);

        hud.is_turbo = gba_turbo_is_active(turbo);
        frame_count++;

        uint64_t now = get_time_us();
        if (now - fps_timer >= 1000000) {
            hud.current_fps = (float)frame_count;
            frame_count = 0;
            fps_timer = now;
        }

        if (!headless && renderer && texture) {
            int win_w, win_h;
            SDL_GetWindowSize(window, &win_w, &win_h);

            /* Update GBA screen texture */
            const uint32_t* pixels = gba_emulator_get_pixels(emu);
            if (pixels) {
                SDL_UpdateTexture(texture, NULL, pixels, GBA_VIDEO_WIDTH * sizeof(uint32_t));
            }

            SDL_SetRenderDrawColor(renderer, 10, 10, 12, 255);
            SDL_RenderClear(renderer);

            /* Calculate 3:2 aspect ratio destination rect */
            int scale_x = win_w / GBA_VIDEO_WIDTH;
            int scale_y = win_h / GBA_VIDEO_HEIGHT;
            int scale = (scale_x < scale_y) ? scale_x : scale_y;
            if (scale < 1) scale = 1;

            int dst_w = GBA_VIDEO_WIDTH * scale;
            int dst_h = GBA_VIDEO_HEIGHT * scale;
            SDL_Rect dst_rect = { (win_w - dst_w) / 2, (win_h - dst_h) / 2, dst_w, dst_h };

            SDL_RenderCopy(renderer, texture, NULL, &dst_rect);

            /* Draw HUD overlay */
            gba_hud_draw(renderer, win_w, win_h, &hud);

            SDL_RenderPresent(renderer);
        }

        /* Timing: Lock to target frame time (16.7ms for 1x, 8.3ms for 2x turbo) */
        uint32_t target_delay = gba_turbo_get_frame_us(turbo);
        uint64_t elapsed = get_time_us() - last_frame_time;
        if (elapsed < target_delay) {
            usleep(target_delay - elapsed);
        }
        last_frame_time = get_time_us();
    }

    printf("[GBA-Crossplay] Cleaning up and exiting...\n");

    gba_discovery_stop_beacon();
    if (socket_fd >= 0) close(socket_fd);
    if (listen_fd >= 0) close(listen_fd);

    gba_emulator_destroy(emu);
    if (dynamic_rom) free(dynamic_rom);

    if (!headless) {
        gba_audio_deinit();
        if (controller) SDL_GameControllerClose(controller);
        if (texture) SDL_DestroyTexture(texture);
        if (renderer) SDL_DestroyRenderer(renderer);
        if (window) SDL_DestroyWindow(window);
        SDL_Quit();
    }

    return 0;
}
