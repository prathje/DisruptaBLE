#if defined(PLATFORM_STM32)
#include "platform/stm32/hal_types.h"
#elif defined(PLATFORM_ZEPHYR)
#include "platform/zephyr/hal_types.h"
#else
#include "platform/posix/hal_types.h"
#endif // PLATFORM_STM32
