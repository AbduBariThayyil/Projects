#include "auth_pam.h"
#include <pthread.h>
#include <security/pam_appl.h>

typedef struct {
    char username[64];
    char password[MAX_PASSWORD_LEN];
    int pipe_fd;
} PamWorkerArgs;

static int pam_conv_callback(int num_msg, const struct pam_message **msg,
                             struct pam_response **resp, void *appdata) {
    if (num_msg <= 0 || num_msg > 32) return PAM_CONV_ERR;

    struct pam_response *aresp = calloc(num_msg, sizeof(struct pam_response));
    if (!aresp) return PAM_BUF_ERR;

    const char *pw = (const char *)appdata;

    for (int i = 0; i < num_msg; i++) {
        if (!msg[i]) continue;
        switch (msg[i]->msg_style) {
            case PAM_PROMPT_ECHO_OFF:
            case PAM_PROMPT_ECHO_ON:
                aresp[i].resp = strdup(pw ? pw : "");
                aresp[i].resp_retcode = 0;
                break;
            case PAM_ERROR_MSG:
            case PAM_TEXT_INFO:
                aresp[i].resp = NULL;
                aresp[i].resp_retcode = 0;
                break;
            default:
                break;
        }
    }

    *resp = aresp;
    return PAM_SUCCESS;
}

static void *pam_worker_thread(void *arg) {
    PamWorkerArgs *args = (PamWorkerArgs *)arg;
    if (!args) return NULL;

    pam_handle_t *pamh = NULL;
    struct pam_conv conv = {
        .conv = pam_conv_callback,
        .appdata_ptr = args->password
    };

    /* Try services in order: "i3lock" (standard lock pam), "system-local-login", "login" */
    const char *services[] = {"i3lock", "system-local-login", "login", NULL};
    int ret = PAM_AUTH_ERR;

    for (int i = 0; services[i]; i++) {
        ret = pam_start(services[i], args->username, &conv, &pamh);
        if (ret == PAM_SUCCESS && pamh) {
            ret = pam_authenticate(pamh, 0);
            if (ret == PAM_SUCCESS) {
                ret = pam_acct_mgmt(pamh, 0);
            }
            pam_end(pamh, ret);
            pamh = NULL;
            break;
        }
        if (pamh) {
            pam_end(pamh, ret);
            pamh = NULL;
        }
    }

    /* Zero sensitive password buffer immediately */
    explicit_bzero(args->password, sizeof(args->password));

    IpcMessage msg;
    memset(&msg, 0, sizeof(msg));
    if (ret == PAM_SUCCESS) {
        msg.code = MSG_PAM_SUCCESS;
    } else {
        msg.code = MSG_PAM_FAILURE;
    }

    /* Send result back to main event loop */
    if (args->pipe_fd >= 0) {
        ssize_t written = write(args->pipe_fd, &msg, sizeof(msg));
        (void)written;
    }

    free(args);
    return NULL;
}

int auth_pam_verify_async(const char *username, const char *password, int pipe_fd) {
    if (!username || !password || pipe_fd < 0) return -1;

    PamWorkerArgs *args = malloc(sizeof(PamWorkerArgs));
    if (!args) return -1;

    memset(args, 0, sizeof(PamWorkerArgs));
    snprintf(args->username, sizeof(args->username), "%s", username);
    snprintf(args->password, sizeof(args->password), "%s", password);
    args->pipe_fd = pipe_fd;

    pthread_t tid;
    int err = pthread_create(&tid, NULL, pam_worker_thread, args);
    if (err != 0) {
        explicit_bzero(args->password, sizeof(args->password));
        free(args);
        return -1;
    }

    pthread_detach(tid);
    return 0;
}
