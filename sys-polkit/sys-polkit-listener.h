#ifndef SYS_POLKIT_LISTENER_H
#define SYS_POLKIT_LISTENER_H

#include "sys-polkit.h"

G_BEGIN_DECLS

#define SYS_POLKIT_TYPE_LISTENER         (sys_polkit_listener_get_type())
#define SYS_POLKIT_LISTENER(o)           (G_TYPE_CHECK_INSTANCE_CAST((o), SYS_POLKIT_TYPE_LISTENER, SysPolkitListener))
#define SYS_POLKIT_LISTENER_CLASS(k)     (G_TYPE_CHECK_CLASS_CAST((k), SYS_POLKIT_TYPE_LISTENER, SysPolkitListenerClass))
#define SYS_POLKIT_IS_LISTENER(o)        (G_TYPE_CHECK_INSTANCE_TYPE((o), SYS_POLKIT_TYPE_LISTENER))
#define SYS_POLKIT_IS_LISTENER_CLASS(k)  (G_TYPE_CHECK_CLASS_TYPE((k), SYS_POLKIT_TYPE_LISTENER))

typedef struct _SysPolkitListener        SysPolkitListener;
typedef struct _SysPolkitListenerClass   SysPolkitListenerClass;

struct _SysPolkitListener {
    PolkitAgentListener parent_instance;
};

struct _SysPolkitListenerClass {
    PolkitAgentListenerClass parent_class;
};

GType                sys_polkit_listener_get_type(void) G_GNUC_CONST;
PolkitAgentListener *sys_polkit_listener_new(void);

G_END_DECLS

#endif /* SYS_POLKIT_LISTENER_H */
