package com.example.cp.model;

import com.mybatisflex.annotation.Column;
import com.mybatisflex.annotation.Id;
import com.mybatisflex.annotation.Table;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDate;
import java.time.LocalDateTime;

/**
 * 试剂信息实体
 *
 * @author cp-team
 * @since 2024-02-10
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Table("cp_resource_info")
public class CpResourceInfo {

    @Id
    @Column("id")
    private String id;

    @Column("reagent_code")
    private String reagentCode;

    @Column("reagent_name")
    private String reagentName;

    @Column("lot_no")
    private String lotNo;

    @Column("vendor")
    private String vendor;

    @Column("vendor_name")
    private String vendorName;

    @Column("item_code")
    private String itemCode;

    @Column("item_name")
    private String itemName;

    @Column("instrument_code")
    private String instrumentCode;

    @Column("production_date")
    private LocalDate productionDate;

    @Column("expiry_date")
    private LocalDate expiryDate;

    @Column("open_date")
    private LocalDate openDate;

    @Column("open_stability_days")
    private Integer openStabilityDays;

    @Column("storage_condition")
    private String storageCondition;

    @Column("reagent_status")
    private Integer reagentStatus;

    @Column("lab_code")
    private String labCode;

    @Column("create_time")
    private LocalDateTime createTime;

    @Column("update_time")
    private LocalDateTime updateTime;

    @Column("is_deleted")
    private Integer isDeleted;
}
