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
 * 诊疗科室实体
 *
 * @author cp-team
 * @since 2024-01-20
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Table("cp_department")
public class CpDepartment {

    @Id
    @Column("id")
    private String id;

    @Column("instrument_code")
    private String instrumentCode;

    @Column("instrument_name")
    private String instrumentName;

    @Column("instrument_model")
    private String instrumentModel;

    @Column("vendor")
    private String vendor;

    @Column("vendor_name")
    private String vendorName;

    @Column("serial_no")
    private String serialNo;

    @Column("lab_code")
    private String labCode;

    @Column("lab_name")
    private String labName;

    @Column("specialty_code")
    private String specialtyCode;

    @Column("specialty_name")
    private String specialtyName;

    @Column("instrument_status")
    private Integer instrumentStatus;

    @Column("lis_code")
    private String lisCode;

    @Column("create_time")
    private LocalDateTime createTime;

    @Column("update_time")
    private LocalDateTime updateTime;

    @Column("is_deleted")
    private Integer isDeleted;
}
