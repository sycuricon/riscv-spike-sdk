#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sys/syscall.h>
#include <sys/wait.h>
#include <unistd.h>

/* This is a test of the existing root-only research interface, not a new
 * arbitrary kernel execution interface. All pages contain a fixed payload. */
struct pv_user_request { uint64_t address, physical, cause; };
#define PV_USER_PROBE _IOWR('V', 0x56, struct pv_user_request)
static const uint32_t payload[] = {0x02a00513, 0x00008067};
static unsigned passed;

static void die(const char *what) { perror(what); exit(1); }

static int expect_error(int fd, unsigned long command, void *arg,
                        int wanted, const char *name)
{
    errno = 0;
    long rc = syscall(SYS_ioctl, fd, command, arg);
    int error = errno;
    if (rc != -1 || error != wanted) {
        fprintf(stderr, "SYSCALL-API FAIL %s rc=%ld errno=%d expected=%d\n",
                name, rc, error, wanted);
        return 0;
    }
    printf("SYSCALL-API PASS %s errno=%d\n", name, error);
    return 1;
}

static void reject(int fd, unsigned long command, void *arg,
                   int wanted, const char *name)
{
    if (!expect_error(fd, command, arg, wanted, name)) exit(1);
    passed++;
}

static void reject_page(int fd, void *page, const char *name)
{
    struct pv_user_request req = {(uintptr_t)page, 0, 0};
    reject(fd, PV_USER_PROBE, &req, EINVAL, name);
    if (req.physical || req.cause) {
        fputs("SYSCALL-API FAIL rejected request changed output\n", stderr);
        exit(1);
    }
}

static void *new_page(long size, int flags)
{
    void *page = mmap(NULL, size, PROT_READ | PROT_WRITE,
                      flags | MAP_ANONYMOUS, -1, 0);
    if (page == MAP_FAILED) die("mmap");
    memcpy(page, payload, sizeof(payload));
    return page;
}

int main(void)
{
    setvbuf(stdout, NULL, _IONBF, 0);
    long size = sysconf(_SC_PAGESIZE);
    if (size != 4096 || geteuid() != 0) {
        fputs("SYSCALL-API FAIL requires root and 4 KiB pages\n", stderr);
        return 1;
    }
    int fd = open("/dev/pvtest", O_RDWR | O_CLOEXEC);
    if (fd < 0) die("open pvtest");
    void *page = new_page(size, MAP_PRIVATE);
    struct pv_user_request req = {0};
    reject(fd, _IO('V', 0x57), &req, ENOTTY, "unknown-command");
    reject(fd, PV_USER_PROBE, NULL, EFAULT, "null-request");
    reject_page(fd, NULL, "zero-address");
    reject_page(fd, (char *)page + 1, "unaligned-address");
    reject_page(fd, (void *)(uintptr_t)(UINT64_MAX & ~((uint64_t)size - 1)),
                "out-of-user-range");
    reject_page(fd, page, "writable-NX-page");
    if (mprotect(page, size, PROT_READ)) die("mprotect R");
    reject_page(fd, page, "read-only-NX-page");
    if (mprotect(page, size, PROT_NONE)) die("mprotect none");
    reject_page(fd, page, "inaccessible-page");
    if (mprotect(page, size, PROT_READ | PROT_WRITE)) die("mprotect RW");
    ((uint32_t *)page)[0] ^= 1;
    if (mprotect(page, size, PROT_READ | PROT_EXEC)) die("mprotect RX");
    reject_page(fd, page, "wrong-fixed-payload");

    void *shared = new_page(size, MAP_SHARED);
    if (mprotect(shared, size, PROT_READ | PROT_EXEC)) die("shared RX");
    reject_page(fd, shared, "shared-page");
    if (munmap(shared, size)) die("munmap shared");
    if (munmap(page, size)) die("munmap page");
    reject_page(fd, page, "unmapped-page");

    /* Keep an already-open fd to exercise the kernel capability check itself;
     * device permissions alone must not be the only protection. */
    fflush(NULL);
    pid_t child = fork();
    if (child < 0) die("fork");
    if (!child) {
        if (setgid(65534) || setuid(65534)) die("drop identity");
        int ok = expect_error(fd, PV_USER_PROBE, &req, EPERM,
                              "unprivileged-inherited-fd");
        _exit(ok ? 0 : 1);
    }
    int status;
    if (waitpid(child, &status, 0) != child) die("waitpid");
    if (!WIFEXITED(status) || WEXITSTATUS(status)) return 1;
    passed++;
    close(fd);
    printf("SYSCALL-API SUMMARY: PASS %u/12 rejection cases\n", passed);
    return passed == 12 ? 0 : 1;
}
