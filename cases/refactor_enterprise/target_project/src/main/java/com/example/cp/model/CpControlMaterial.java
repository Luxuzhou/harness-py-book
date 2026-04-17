package com.example.cp.model;

import com.mybatisflex.annotation.Column;
import com.mybatisflex.annotation.Id;
import com.mybatisflex.annotation.Table;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;

/**
 * 临床路径品信息实体
 *
 * @author cp-team
 * @since 2024-02-10
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Table("cp_control_material")
public class CpControlMaterial {

    @Id
    @Column("id")
    private String id;

    @Column("lot_no")
    private String lotNo;

    @Column("control_name")
    private String controlName;

    @Column("vendor")
    private String vendor;

    @Column("vendor_name")
    private String vendorName;

    @Column("level_count")
    private Integer levelCount;

    @Column("expiry_date")
    private LocalDate expiryDate;

    @Column("storage_condition")
    private String storageCondition;

    @Column("is_active")
    private Integer isActive;

    @Column("lab_code")
    private String labCode;

    @Column("create_time")
    private LocalDateTime createTime;

    @Column("update_time")
    private LocalDateTime updateTime;

    @Column("is_deleted")
    private Integer isDeleted;
}
