import psutil
import time

class SystemMonitor:
    @staticmethod
    def get_system_stats():
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Get network stats
        net_io = psutil.net_io_counters()
        
        # Get load averages
        load_avg = psutil.getloadavg()
        
        return {
            "cpu": {
                "usage_percent": cpu_percent,
                "load_average": {
                    "1min": load_avg[0],
                    "5min": load_avg[1],
                    "15min": load_avg[2]
                }
            },
            "memory": {
                "total": memory.total,
                "available": memory.available,
                "used": memory.used,
                "free": memory.free,
                "percent": memory.percent
            },
            "disk": {
                "total": disk.total,
                "used": disk.used,
                "free": disk.free,
                "percent": disk.percent
            },
            "network": {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_sent": net_io.packets_sent,
                "packets_recv": net_io.packets_recv,
                "errors_in": net_io.errin,
                "errors_out": net_io.errout
            },
            "processes": len(psutil.pids()),
            "boot_time": psutil.boot_time()
        }

    @staticmethod
    def get_process_info(pid):
        try:
            process = psutil.Process(pid)
            return {
                "name": process.name(),
                "status": process.status(),
                "cpu_percent": process.cpu_percent(),
                "memory_percent": process.memory_percent(),
                "create_time": process.create_time(),
                "cmdline": process.cmdline(),
                "num_threads": process.num_threads()
            }
        except psutil.NoSuchProcess:
            return None