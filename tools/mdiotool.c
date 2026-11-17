/* Minimal clause-22 MDIO read/write via the kernel SIOCGMIIREG/SIOCSMIIREG path.
 * Usage:
 *   mdiotool IFACE PHY REG            read reg
 *   mdiotool IFACE PHY REG VALUE      write reg (hex or dec)
 *   mdiotool IFACE PHY dump           read regs 0..31
 *   mdiotool IFACE PHY page PAGE REG [VALUE]   select page (reg31) then access REG
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <net/if.h>
#include <linux/mii.h>
#include <linux/sockios.h>

static int fd;
static char ifname[IFNAMSIZ];

static int xfer(int phy, int reg, int write, int val, int *out)
{
    struct mii_ioctl_data d;
    struct ifreq ifr;
    memset(&d, 0, sizeof(d));
    d.phy_id = phy;
    d.reg_num = reg;
    d.val_in = val;
    memset(&ifr, 0, sizeof(ifr));
    strncpy(ifr.ifr_name, ifname, IFNAMSIZ - 1);
    ifr.ifr_data = (void *)&d;
    if (ioctl(fd, write ? SIOCSMIIREG : SIOCGMIIREG, &ifr) < 0) {
        perror("ioctl");
        return -1;
    }
    *out = d.val_out;
    return 0;
}

static long num(const char *s) { return strtol(s, NULL, 0); }

int main(int argc, char **argv)
{
    if (argc < 4) {
        fprintf(stderr, "usage: %s IFACE PHY REG|dump|page ...\n", argv[0]);
        return 2;
    }
    strncpy(ifname, argv[1], IFNAMSIZ - 1);
    int phy = num(argv[2]);
    fd = socket(AF_INET, SOCK_DGRAM, 0);
    if (fd < 0) { perror("socket"); return 1; }

    if (strcmp(argv[3], "id") == 0) {
        struct mii_ioctl_data d; struct ifreq ifr;
        memset(&d, 0, sizeof(d)); memset(&ifr, 0, sizeof(ifr));
        strncpy(ifr.ifr_name, ifname, IFNAMSIZ - 1);
        ifr.ifr_data = (void *)&d;
        int r = ioctl(fd, SIOCGMIIPHY, &ifr);
        printf("SIOCGMIIPHY ret=%d attached phy_id=%d\n", r, d.phy_id);
        for (int reg = 2; reg <= 3; reg++) {
            int v = -1; int rr = xfer(d.phy_id, reg, 0, 0, &v);
            printf("  read phy%d reg%d ret=%d val=0x%04x\n", d.phy_id, reg, rr, v);
        }
        return 0;
    }
    if (strcmp(argv[3], "dump") == 0) {
        for (int r = 0; r < 32; r++) {
            int v = 0;
            if (xfer(phy, r, 0, 0, &v) == 0)
                printf("phy%d reg%02d = 0x%04x\n", phy, r, v);
        }
        return 0;
    }
    if (strcmp(argv[3], "page") == 0) {
        if (argc < 6) { fprintf(stderr, "page PAGE REG [VALUE]\n"); return 2; }
        int page = num(argv[4]);
        int reg = num(argv[5]);
        int v = 0;
        if (xfer(phy, 31, 1, page, &v) < 0) return 1;   /* select page */
        if (argc >= 7) {
            if (xfer(phy, reg, 1, num(argv[6]), &v) < 0) return 1;
            printf("phy%d page0x%x reg%02d <= 0x%04x\n", phy, page, reg, v);
        } else {
            if (xfer(phy, reg, 0, 0, &v) < 0) return 1;
            printf("phy%d page0x%x reg%02d = 0x%04x\n", phy, page, reg, v);
        }
        xfer(phy, 31, 1, 0, &v);                          /* back to page 0 */
        return 0;
    }
    int reg = num(argv[3]);
    int v = 0;
    if (argc >= 5) {
        if (xfer(phy, reg, 1, num(argv[4]), &v) < 0) return 1;
        printf("phy%d reg%02d <= 0x%04x\n", phy, reg, v);
    } else {
        if (xfer(phy, reg, 0, 0, &v) < 0) return 1;
        printf("phy%d reg%02d = 0x%04x\n", phy, reg, v);
    }
    return 0;
}
