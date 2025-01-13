// PEC Patch
#define CRDAK(dest, src, context) __asm__ __volatile__( \
    "crdak %[dest_reg], %[src_reg], %[context_reg], 0, 7"     \
    : [ dest_reg ] "=r"(dest)                           \
    : [ src_reg ] "r"(src), [ context_reg ] "r"(context))
#define CREAK(dest, src, context) __asm__ __volatile__( \
    "creak %[dest_reg], %[src_reg], %[context_reg], 0, 7"     \
    : [ dest_reg ] "=r"(dest)                           \
    : [ src_reg ] "r"(src), [ context_reg ] "r"(context))
#define CRDBK(dest, src, context) __asm__ __volatile__( \
    "crdbk %[dest_reg], %[src_reg], %[context_reg], 0, 7"     \
    : [ dest_reg ] "=r"(dest)                           \
    : [ src_reg ] "r"(src), [ context_reg ] "r"(context))
#define CREBK(dest, src, context) __asm__ __volatile__( \
    "crebk %[dest_reg], %[src_reg], %[context_reg], 0, 7"     \
    : [ dest_reg ] "=r"(dest)                           \
    : [ src_reg ] "r"(src), [ context_reg ] "r"(context))
#define CRDTK(dest, src, context) __asm__ __volatile__( \
    "crdtk %[dest_reg], %[src_reg], %[context_reg], 0, 7"     \
    : [ dest_reg ] "=r"(dest)                           \
    : [ src_reg ] "r"(src), [ context_reg ] "r"(context))
#define CRETK(dest, src, context) __asm__ __volatile__( \
    "cretk %[dest_reg], %[src_reg], %[context_reg], 0, 7"     \
    : [ dest_reg ] "=r"(dest)                           \
    : [ src_reg ] "r"(src), [ context_reg ] "r"(context))
#define CRDMK(dest, src, context) __asm__ __volatile__( \
    "crdmk %[dest_reg], %[src_reg], %[context_reg], 0, 7"     \
    : [ dest_reg ] "=r"(dest)                           \
    : [ src_reg ] "r"(src), [ context_reg ] "r"(context))
#define CREMK(dest, src, context) __asm__ __volatile__( \
    "cremk %[dest_reg], %[src_reg], %[context_reg], 0, 7"     \
    : [ dest_reg ] "=r"(dest)                           \
    : [ src_reg ] "r"(src), [ context_reg ] "r"(context))