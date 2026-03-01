"""RBAC — Role-Based Access Control for HydroClaw.
基于角色的访问控制。

Five preset roles for water network operations:
- operator (运维): Real-time monitoring, dispatch, four-prediction, alerts
- designer (设计): Control design, optimization, sensitivity analysis
- researcher (科研): Simulation, data analysis, literature, paper writing
- admin (管理): Full access, system configuration
- teacher (教学): Teaching scenarios, guided exploration, controlled experiments
"""

from hydroclaw.rbac.manager import RBACManager, Role, Permission

__all__ = ["RBACManager", "Role", "Permission"]
