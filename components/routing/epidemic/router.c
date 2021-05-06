#include "routing/epidemic/router.h"



static struct router_config RC = {
};

struct router_config router_get_config(void)
{
    return RC;
}


enum ud3tn_result router_update_config(struct router_config conf)
{
    // configuration not yet supported
    (void)conf;
    return UD3TN_OK;
}