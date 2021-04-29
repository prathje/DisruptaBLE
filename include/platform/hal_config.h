#if defined(PLATFORM_STM32)
#include "platform/stm32/hal_config.h"
#elif defined(PLATFORM_ZEPHYR)
#include "platform/zephyr/hal_config.h"
#else
#include "platform/posix/hal_config.h"
#endif