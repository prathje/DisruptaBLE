#ifndef HAL_TYPES_H_INCLUDED
#define HAL_TYPES_H_INCLUDED

#include <kernel.h>

#define QueueIdentifier_t struct k_msgq *
#define Semaphore_t struct k_sem *
#define Task_t k_tid_t

#endif // HAL_TYPES_H_INCLUDED
