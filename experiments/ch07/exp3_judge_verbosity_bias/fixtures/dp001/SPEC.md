# validate_user 规约

`validate_user(data: dict)` 必须检查下面 4 类规则，把全部错误收集进返回列表（不要发现一条就 return）：

1. `username`：必须存在且非空字符串。错误信息：`"username is required"`
2. `email`：必须存在；必须包含 `@`。错误信息：`"email is required"` 或 `"email must contain @"`
3. `age`：可选；若提供则必须是 0 到 150 之间的整数。错误信息：`"age must be between 0 and 150"`
4. `role`：可选；若提供则必须是 `admin`、`user`、`guest` 之一。错误信息：`"role must be one of admin/user/guest"`

测试只覆盖了规则 1 和规则 2 的常见 case，规则 3、4 在线上偶发出错。
