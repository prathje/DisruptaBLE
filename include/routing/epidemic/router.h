#ifndef ROUTER_H_INCLUDED
#define ROUTER_H_INCLUDED

#include "ud3tn/bundle.h"
#include "ud3tn/config.h"
#include "ud3tn/node.h"

#include <stddef.h>
#include <stdint.h>

struct router_config {
};

struct router_config router_get_config(void);
enum ud3tn_result router_update_config(struct router_config config);

#endif /* ROUTER_H_INCLUDED */
