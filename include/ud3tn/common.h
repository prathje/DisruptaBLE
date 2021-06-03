#ifndef UD3TN_COMMON_H_INCLUDED
#define UD3TN_COMMON_H_INCLUDED

#include <string.h>


/* COMMON FUNCTIONS */

#define count_list_next_length(list, cnt) do { \
	if (list != NULL) \
		cnt = 1; \
	iterate_list_next(list) { ++cnt; } \
} while (0)

#define iterate_list_next(list) \
	for (; list; list = (list)->next)

#define list_element_free(list) do { \
	void *e = list->next; \
	free(list); \
	list = e; \
} while (0)

#define list_free(list) { \
while (list != NULL) { \
	list_element_free(list); \
} }


// Zephyr already includes the following macros but just defines them...
#ifdef PLATFORM_ZEPHYR
#include <sys/util.h>
#include <toolchain.h>
#endif

#ifndef MIN
#define MIN(a,b) (((a)<(b))?(a):(b))
#endif

#ifndef MAX
#define MAX(a,b) (((a)>(b))?(a):(b))
#endif

#ifndef Z_MIN
#define Z_MIN(a, b) ({ \
	__typeof__(a) _a = (a); \
	__typeof__(b) _b = (b); \
	_b < _a ? _b : _a; \
})
#endif


#ifndef Z_MAX
#define Z_MAX(a, b) ({ \
	__typeof__(a) _a = (a); \
	__typeof__(b) _b = (b); \
	_b > _a ? _b : _a; \
})
#endif

#ifndef CLAMP
#define CLAMP(val, low, high) (((val) <= (low)) ? (low) : MIN(val, high))
#endif

#ifndef Z_CLAMP
#define Z_CLAMP(val, low, high) ({                                             \
		/* random suffix to avoid naming conflict */                   \
		__typeof__(val) _value_val_ = (val);                           \
		__typeof__(low) _value_low_ = (low);                           \
		__typeof__(high) _value_high_ = (high);                        \
		(_value_val_ < _value_low_)  ? _value_low_ :                   \
		(_value_val_ > _value_high_) ? _value_high_ :                  \
					       _value_val_;                    \
	})
#endif


#define HAS_FLAG(value, flag) ((value & flag) != 0)


#define ARRAY_LENGTH(x) (sizeof(x) / sizeof((x)[0]))

#ifndef PLATFORM_ZEPHYR
#define ARRAY_SIZE ARRAY_LENGTH
#endif

#if defined(__GNUC__) && (__GNUC__ >= 7) && !defined(__clang__)
#define fallthrough __attribute__ ((fallthrough))
#else
#define fallthrough
#endif

/* ASSERT */

#if defined(DEBUG)

#include <assert.h>

#define ASSERT(value) assert(value)

#else /* DEBUG */

// FIXME: A lot of cases are reported by clang-tidy in which an assertion may
// not be met, resulting in invalid pointers. Before they are fixed, this has
// to stay a check for all builds to ensure a reliable abort() if an
// assertion cannot be met.

// #define ASSERT(value) ((void)(value))

#include <assert.h>

#define ASSERT(value) assert(value)

#endif /* DEBUG */

#endif /* UD3TN_COMMON_H_INCLUDED */
