# 现有系统架构说明

## 1. 系统全景

```
+------------------+          REST API          +--------------------+
|   H34 (Java)     | <----------------------->  |   S37 (Python)     |
|   Spring Boot    |                            |   FastAPI          |
|   质控规则管理   |                            |   质控数据分析     |
|   数据持久化     |                            |   算法引擎         |
+--------+---------+                            +---------+----------+
         |                                                |
    +----v----+                                    +------v------+
    |  MySQL  |                                    |  内存计算    |
    |  持久层 |                                    |  (NumPy等)  |
    +---------+                                    +-------------+
```

## 2. H34 — Java 质控管理平台

### 2.1 技术栈
- Java 17 + Spring Boot 3.x
- Spring Data JPA（Hibernate）
- MySQL 8.0
- Maven 构建
- Swagger/OpenAPI 文档生成

### 2.2 项目结构
```
com.example.sqc/
├── controller/     # REST API 控制器（@RestController）
├── service/        # 业务逻辑层（@Service）
├── dao/
│   ├── model/      # JPA 实体类（@Entity）
│   └── repository/ # Spring Data 仓库接口
├── dto/            # 数据传输对象（请求/响应）
├── config/         # Spring 配置类
└── exception/      # 全局异常处理
```

### 2.3 编码规范
- Controller 只做参数校验和响应封装，业务逻辑在 Service 层
- 数据库实体与 DTO 严格分离，通过手写 mapper 或 MapStruct 转换
- API 路径前缀：`/api/v1/`
- 字段命名：Java 代码使用 camelCase，JSON 序列化使用 snake_case
  （通过 `spring.jackson.property-naming-strategy=SNAKE_CASE` 配置）
- 异常处理：统一通过 `@RestControllerAdvice` 返回 ErrorResponse

### 2.4 现有模块
- 质控品管理（CRUD）
- Westgard 规则管理
- 质控数据录入
- （新增）智能报警规则管理 <-- 本次开发

## 3. S37 — Python 质控分析引擎

### 3.1 技术栈
- Python 3.11 + FastAPI
- NumPy（数值计算）
- httpx（HTTP 客户端，调用 H34 API）
- Pydantic v2（数据校验）
- pytest（测试框架）

### 3.2 项目结构
```
app/
├── api/
│   └── endpoints.py    # FastAPI 路由定义
├── services/
│   └── analyzer.py     # 分析算法实现
├── models/
│   └── schemas.py      # Pydantic 数据模型
├── clients/
│   └── h34_client.py   # 调用 H34 Java 端的 HTTP 客户端
└── core/
    └── config.py       # 配置管理
```

### 3.3 编码规范
- 路由函数使用 async def
- 业务逻辑在 services/ 层，路由只做请求解析和响应封装
- 所有数据模型使用 Pydantic BaseModel
- 字段命名统一使用 snake_case
- 调用外部服务使用 httpx.AsyncClient

### 3.4 现有模块
- Levey-Jennings 图表数据生成
- Westgard 规则判定
- 统计分析（均值、SD、CV%）
- （新增）智能报警分析 <-- 本次开发

## 4. 系统间通信

### 4.1 通信模式
- 同步 REST API 调用（JSON over HTTP）
- Python 端作为客户端调用 Java 端的 API
- Java 端也可以通过 webhook 回调 Python 端（本次暂不涉及）

### 4.2 认证机制
- 内部服务间使用 `X-Service-Token` 头部认证
- Token 通过配置文件注入，不硬编码

### 4.3 调用链追踪
- 通过 `X-Trace-Id` 头部传递追踪ID
- Python 端生成 traceId，Java 端接收并记录到日志

## 5. 开发环境

### 5.1 本地运行
- H34: `mvn spring-boot:run`（端口 8080）
- S37: `uvicorn app.main:app --port 8000`

### 5.2 测试
- H34: `mvn test`
- S37: `pytest`
