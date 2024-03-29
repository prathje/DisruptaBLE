/*
 * hal_config.h
 *
 * Description: contains platform-specific configuration information
 *
 */

#ifndef HAL_CONFIG_H_INCLUDED
#define HAL_CONFIG_H_INCLUDED

#define CONTACT_RX_TASK_PRIORITY 3
#define ROUTER_TASK_PRIORITY 3
#define BUNDLE_PROCESSOR_TASK_PRIORITY 3
#define CONTACT_MANAGER_TASK_PRIORITY 2
#define CONTACT_TX_TASK_PRIORITY 4
#define ROUTER_OPTIMIZER_TASK_PRIORITY 1

// TODO: Rework these
#define CONTACT_LISTEN_TASK_PRIORITY 3
#define CONTACT_MANAGEMENT_TASK_PRIORITY 3

#define ROUTING_AGENT_TASK_PRIORITY 3

#define DEFAULT_TASK_STACK_SIZE 4096
#define CONTACT_RX_TASK_STACK_SIZE 4096
#define CONTACT_MANAGER_TASK_STACK_SIZE 4096
#define ROUTER_OPTIMIZER_TASK_STACK_SIZE 4096
#define CONTACT_TX_TASK_STACK_SIZE 4096
#define CONTACT_ROUTER_TASK_STACK_SIZE 4096

#define CONTACT_LISTEN_TASK_STACK_SIZE 4096
#define CONTACT_MANAGEMENT_TASK_STACK_SIZE 4096

// Timeout for transmitting the next byte. Specified in ms. -1 means infinite.
#define COMM_TX_TIMEOUT -1
// Timeout for receiving further data after at least one byte was received
// Note that using a large timeout will commonly delay bundle reception for
// this amount of time. Specified in ms.
#define COMM_RX_TIMEOUT 100

#endif /* HAL_CONFIG_H_INCLUDED */
