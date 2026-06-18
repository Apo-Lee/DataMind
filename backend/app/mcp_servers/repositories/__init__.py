# -*- coding: utf-8 -*-
from .base import BaseRepository
from .employee_repo import EmployeeRepository
from .customer_repo import CustomerRepository

from .finance_repo import FinanceRepository
from .erp_repo import ErpRepository
from .department_repo import DepartmentRepository

__all__ = [
    "BaseRepository", "EmployeeRepository", "CustomerRepository",
    "FinanceRepository", "ErpRepository", "DepartmentRepository",
]
