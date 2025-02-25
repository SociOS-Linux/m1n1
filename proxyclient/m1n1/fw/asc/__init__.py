# SPDX-License-Identifier: MIT
from ...utils import *

from .crash import ASCCrashLogEndpoint
from .syslog import ASCSysLogEndpoint
from .mgmt import ASCManagementEndpoint
from .kdebug import ASCKDebugEndpoint
from .ioreporting import ASCIOReportingEndpoint
from .oslog import ASCOSLogEndpoint
from .base import ASCBaseEndpoint, ASCTimeout
from ...hw.asc import ASC

__all__ = []

class ASCDummyEndpoint(ASCBaseEndpoint):
    SHORT = "dummy"

class StandardASC(ASC):
    ENDPOINTS = {
        0: ASCManagementEndpoint,
        1: ASCCrashLogEndpoint,
        2: ASCSysLogEndpoint,
        3: ASCKDebugEndpoint,
        4: ASCIOReportingEndpoint,
        8: ASCOSLogEndpoint,
        0xa: ASCDummyEndpoint, # tracekit
    }

    def __init__(self, u, asc_base, dart=None):
        super().__init__(u, asc_base)
        self.remote_eps = set()
        self.add_ep(0, ASCManagementEndpoint(self, 0))
        self.dart = dart
        self.eps = []
        self.epcls = {}
        self.dva_offset = 0

        for cls in type(self).mro():
            eps = getattr(cls, "ENDPOINTS", None)
            if eps is None:
                break
            for k, v in eps.items():
                if k not in self.epcls:
                    self.epcls[k] = v

    def iomap(self, addr, size):
        if self.dart is None:
            return addr
        dva = self.dva_offset | self.dart.iomap(0, addr, size)

        self.dart.invalidate_streams(1)
        return dva

    def ioalloc(self, size):
        paddr = self.u.memalign(0x4000, size)
        dva = self.iomap(paddr, size)
        return paddr, dva

    def ioread(self, dva, size):
        if self.dart:
            return self.dart.ioread(0, dva & 0xFFFFFFFF, size)
        else:
            return self.iface.readmem(dva, size)

    def iowrite(self, dva, data):
        if self.dart:
            return self.dart.iowrite(0, dva & 0xFFFFFFFF, data)
        else:
            return self.iface.writemem(dva, data)

    def start_ep(self, epno):
        if epno not in self.epcls:
            raise Exception(f"Unknown endpoint {epno:#x}")

        epcls = self.epcls[epno]
        ep = epcls(self, epno)
        self.add_ep(epno, ep)
        print(f"Starting endpoint #{epno:#x} ({ep.name})")
        self.mgmt.start_ep(epno)
        ep.start()

    def start(self):
        if self.is_running():
            self.mgmt.start()
        else:
            self.boot()
        self.mgmt.wait_boot(1)

    def stop(self, state=0x10):
        for ep in list(self.epmap.values())[::-1]:
            if ep.epnum < 0x10:
                continue
            ep.stop()
        self.mgmt.stop(state=state)
        self.epmap = {}
        self.add_ep(0, ASCManagementEndpoint(self, 0))

    def boot(self):
        print("Booting ASC...")
        super().boot()
        self.mgmt.wait_boot()

__all__.extend(k for k, v in globals().items()
               if (callable(v) or isinstance(v, type)) and v.__module__ == __name__)
