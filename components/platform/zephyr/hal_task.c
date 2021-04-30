/*
 * hal_task.c
 *
 * Description: contains the stm32-implementation of the hardware
 * abstraction layer interface for thread-related functionality
 *
 */

#include "platform/hal_task.h"

#include "ud3tn/common.h"
#include <zephyr.h>


struct zephyr_task *hal_task_create(void (*task_function)(void *), const char *task_name,
		    int task_priority, void *task_parameters,
		    size_t task_stack_size, void *task_tag)
{
	/* ensure that an actual function is provided for thread creation */
	ASSERT(task_function != NULL);

    struct zephyr_task *task = k_malloc(sizeof(struct zephyr_task));

    if (task == NULL) {
        return NULL;
    }

    uint32_t stack_size = task_stack_size + CONFIG_TEST_EXTRA_STACKSIZE;

    // TODO: This is currently based on https://github.com/zephyrproject-rtos/zephyr/issues/26999, use stack allocation api when available
    task->stack = k_aligned_alloc(Z_KERNEL_STACK_OBJ_ALIGN, Z_KERNEL_STACK_SIZE_ADJUST(stack_size));

    task->tid = k_thread_create(
                            &task->thread,
                            task->stack,
                            stack_size,
                            (k_thread_entry_t) task_function,
                            task_parameters,
                            NULL,
                            NULL,
                            task_priority,
                            K_INHERIT_PERMS,
                            K_NO_WAIT
    );

    if (task->tid  == NULL) {
        k_free(task->stack);
        k_free(task);
        return NULL;
    }

    // We will use the default system pool for now (in user mode we would want to create separate heap regions!)
    k_thread_system_pool_assign(task->tid);

    // TODO: How to name them?
    // TODO: How to tag them?

	return task;
}

void hal_task_start_scheduler(void)
{
	// NO scheduler start required for Zephyr
}

void hal_task_delay(int delay)
{
    k_msleep(delay);
}


void hal_task_delete(struct zephyr_task *task)
{
    k_thread_abort(task->tid); // TODO: Do we need to ensure that the thread is not running anymore?
    k_free(task->stack);
    k_free(task);
}
