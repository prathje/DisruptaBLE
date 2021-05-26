#ifndef HAL_TYPES_H_INCLUDED
#define HAL_TYPES_H_INCLUDED

#include <kernel.h>
#include "zephyr_stub.h"


struct zephyr_task {
    struct k_thread thread;
    k_tid_t tid;
    k_thread_stack_t *stack;    // needs to be freed before task is freed!
};


#define QueueIdentifier_t struct k_msgq *
#define Semaphore_t struct k_sem *
#define Task_t struct zephyr_task*

#endif // HAL_TYPES_H_INCLUDED
