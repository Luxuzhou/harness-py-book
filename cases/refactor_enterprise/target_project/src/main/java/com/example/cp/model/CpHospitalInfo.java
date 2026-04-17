package com.example.cp.model;

import com.mybatisflex.annotation.Column;
import com.mybatisflex.annotation.Id;
import com.mybatisflex.annotation.Table;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

/**
 * 实验室信息实体
 *
 * @author cp-team
 * @since 2024-01-15
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Table("cp_hospital_info")
public class CpHospitalInfo {

    @Id
    @Column("id")
    private String id;

    @Column("lab_code")
    private String labCode;

    @Column("lab_name")
    private String labName;

    @Column("hospital_code")
    private String hospitalCode;

    @Column("hospital_name")
    private String hospitalName;

    @Column("lab_level")
    private Integer labLevel;

    @Column("address")
    private String address;

    @Column("contact_person")
    private String contactPerson;

    @Column("contact_phone")
    private String contactPhone;

    @Column("lab_status")
    private Integer labStatus;

    @Column("create_time")
    private LocalDateTime createTime;

    @Column("update_time")
    private LocalDateTime updateTime;

    @Column("is_deleted")
    private Integer isDeleted;
}
