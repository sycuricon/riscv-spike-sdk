// Copyright (c) 2019-2022 Phantom1003

#include <linux/init.h>
#include <linux/module.h>
#include <linux/kernel.h>

MODULE_LICENSE("GPL");

#define MAX_LENGTH 64
#define subcells sbox[sbox_use]
#define subcells_inv sbox_inv[sbox_use]

typedef unsigned long long int const_t;
typedef unsigned long long int tweak_t;
typedef unsigned long long int text_t;
typedef unsigned long long int qkey_t;
typedef unsigned char          cell_t;

static int __init rgvlt_init(void);
static void __exit rgvlt_exit(void);

static void __exit rgvlt_exit(void) {
	printk(KERN_INFO "Exit...");
}

static int __init rgvlt_init(void) {
	text_t plaintext = 0xfb623599da6e8127;
	qkey_t w0 = 0x84be85ce9804e94b;
	qkey_t k0 = 0xec2802d4e0a488e9;
	tweak_t tweak = 0x477d469dec0b8762;
	text_t ciphertext;

	printk(KERN_INFO "QARMA64  Plaintext = 0x%016llx\nKey = 0x%016llx || 0x%016llx\nTweak = 0x%016llx\n\n", plaintext, w0, k0, tweak);
	
	asm volatile (
		"csrw 0x5f0, %[k0]\n"
		"csrw 0x5f1, %[w0]\n"
		:
		:[w0] "r" (w0), [k0] "r" (k0)
		:
	);
	printk(KERN_INFO "k0, w0 write done\n");
	
	qkey_t read_k0 = 0;
	qkey_t read_w0 = 0;
	asm volatile (
		"csrr %[read_k0], 0x5f0\n"
		"csrr %[read_w0], 0x5f1\n"
		:[read_w0] "=r" (read_w0), [read_k0] "=r" (read_k0)
		:
		:
	);
	printk(KERN_INFO "read_w0 = 0x%llx, read_k0 = 0x%llx", read_w0, read_k0);

	asm volatile (
		"csrw 0x5f0, %[k0]\n"
		"csrw 0x5f1, %[w0]\n"
		"mv t0, %[plaintext]\n"
		"mv t1, %[tweak]\n"
		"li t2, 0\n"
		".insn r 0x6b, 0x0, 0x54, t2, t0, t1\n"
		"mv %[ciphertext], t2\n"
		:[ciphertext] "=r" (ciphertext)
		:[tweak] "r" (tweak), [plaintext] "r" (plaintext), [w0] "r" (w0), [k0] "r" (k0)
		:"t0", "t1", "t2"
	);

	printk(KERN_INFO "Ciphertext = 0x%016llx", ciphertext);

	text_t decrypttext;
	asm volatile (
		"mv t0, %[ciphertext]\n"
		"mv t1, %[tweak]\n"
		"li t2, 0\n"
		".insn r 0x6b, 0x0, 0x55, t2, t0, t1\n"
		"mv %[decrypttext], t2\n"
		:[decrypttext] "=r" (decrypttext)
		:[ciphertext] "r" (ciphertext), [tweak] "r" (tweak)
		:"t0", "t1", "t2"
	);
	printk(KERN_INFO "Decrypttext  = 0x%016llx\n", decrypttext);
	return 0;
}

module_init(rgvlt_init);
module_exit(rgvlt_exit);
MODULE_LICENSE("GPL");