#include <asm/current.h>
void panic(const char *fmt, ...);
void show_stack(struct task_struct *task, unsigned long *sp, const char *loglvl);

#define CRDAK(dest, src, context) __asm__ __volatile__( \
    "crdak %[dest_reg], %[src_reg], %[context_reg], 0, 7"     \
    : [ dest_reg ] "=r"(dest)                           \
    : [ src_reg ] "r"(src), [ context_reg ] "r"(context))
#define CREAK(dest, src, context) __asm__ __volatile__( \
    "creak %[dest_reg], %[src_reg], %[context_reg], 0, 7"     \
    : [ dest_reg ] "=r"(dest)                           \
    : [ src_reg ] "r"(src), [ context_reg ] "r"(context))
#define GET_RETADDR(callAddr) __asm__ __volatile__( \
    "ld %[callAddr], -8(s0)"                        \
    : [ callAddr ] "=r"(callAddr))

unsigned long long decryptFunc(unsigned long long value, unsigned long long *addr)
{
    unsigned long ret, *sp, callAddr;
    // GET_RETADDR(callAddr);
    if (value == 0)
    {
        // printk("decrypt 0 at 0x%lx, callAddr: 0x%lx\n", addr, callAddr);
        // __asm__ __volatile__(
        //     "move %[sp], sp"
        //     : [ sp ] "=r"(sp));
        // show_stack(get_current(), sp, 0);
        return 0;
    }
    CRDAK(ret, value, addr);
    // if (ret >= 200 && ret < 0xffffffd000000000)
    // {
    //     printk("Decrypt wrong fp: encrypted-value 0x%lx, decrypted-value 0x%lx, address 0x%lx", value, ret, addr);
    //     printk("Call Address: 0x%lx", callAddr);
    //     panic("Decrypt wrong fp");
    // }
    return ret;
}
unsigned long long encryptFunc(unsigned long long value, unsigned long long *addr)
{
    unsigned long long ret;
    unsigned long long callAddr;
    GET_RETADDR(callAddr);
    if (value >= 200 && value < 0xffffffd000000000)
    {
        printk("Encrypt wrong fp: encrypted-value 0x%lx, addr 0x%lx", value, addr);
        printk("Call Address: 0x%lx", callAddr);
        panic("Encrypt wrong fp");
    }
    CREAK(ret, value, addr);
    return ret;
}
unsigned long long decryptFuncNoCheck(unsigned long long value, unsigned long long *addr)
{
    unsigned long long ret;
    CRDAK(ret, value, addr);
    return ret;
}
unsigned long long encryptFuncNoCheck(unsigned long long value, unsigned long long *addr)
{
    unsigned long long ret;
    CREAK(ret, value, addr);
    return ret;
}

typedef void (*gfp_initcall_t)(void);
extern gfp_initcall_t _GFPInitFP_start, _GFPInitFP_end;
void __init PPPGFPInit(void)
{
    gfp_initcall_t *fpp = &_GFPInitFP_start;
    do
    {
        (*fpp)();
    } while (++fpp < &_GFPInitFP_end);
}

typedef void (*perCPUCopy_t)(void *, void *);
extern perCPUCopy_t _perCPUCopy_start, _perCPUCopy_end;
void perCPUCopy(void *dest, void *src)
{
    perCPUCopy_t *fpp = &_perCPUCopy_start;
    do
    {
        (*fpp)(dest, src);
    } while (++fpp < &_perCPUCopy_end);
}
