#ifndef CLA_ML2CAP
#define CLA_ML2CAP

#include "cla/cla.h"

#include "ud3tn/bundle_agent_interface.h"

#include <stddef.h>


struct cla_config *ml2cap_create(
	const char *const options[], const size_t option_count,
	const struct bundle_agent_interface *bundle_agent_interface);

#endif