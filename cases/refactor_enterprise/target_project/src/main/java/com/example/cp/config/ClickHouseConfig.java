package com.example.cp.config;

import com.zaxxer.hikari.HikariDataSource;
import org.apache.ibatis.session.SqlSessionFactory;
import org.mybatis.spring.SqlSessionFactoryBean;
import org.mybatis.spring.SqlSessionTemplate;
import org.mybatis.spring.annotation.MapperScan;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import javax.sql.DataSource;

/**
 * ClickHouse数据源配置
 * <p>
 * 配置独立的ClickHouse数据源，用于查询诊疗结果宽表。
 * 与主MySQL数据源隔离，使用独立的SqlSessionFactory。
 * </p>
 *
 * @author cp-team
 * @since 2024-01-10
 */
@Configuration
@MapperScan(basePackages = "com.example.cp.mapper.ck",
        sqlSessionFactoryRef = "clickHouseSqlSessionFactory")
public class ClickHouseConfig {

    @Value("${spring.datasource.clickhouse.url}")
    private String url;

    @Value("${spring.datasource.clickhouse.username}")
    private String username;

    @Value("${spring.datasource.clickhouse.password}")
    private String password;

    @Value("${spring.datasource.clickhouse.driver-class-name:com.clickhouse.jdbc.ClickHouseDriver}")
    private String driverClassName;

    @Bean("clickHouseDataSource")
    public DataSource clickHouseDataSource() {
        HikariDataSource dataSource = new HikariDataSource();
        dataSource.setJdbcUrl(url);
        dataSource.setUsername(username);
        dataSource.setPassword(password);
        dataSource.setDriverClassName(driverClassName);
        dataSource.setMaximumPoolSize(10);
        dataSource.setMinimumIdle(2);
        dataSource.setConnectionTimeout(30000);
        dataSource.setIdleTimeout(600000);
        dataSource.setMaxLifetime(1800000);
        return dataSource;
    }

    @Bean("clickHouseSqlSessionFactory")
    public SqlSessionFactory clickHouseSqlSessionFactory(
            @Qualifier("clickHouseDataSource") DataSource dataSource) throws Exception {
        SqlSessionFactoryBean factoryBean = new SqlSessionFactoryBean();
        factoryBean.setDataSource(dataSource);
        return factoryBean.getObject();
    }

    @Bean("clickHouseSqlSessionTemplate")
    public SqlSessionTemplate clickHouseSqlSessionTemplate(
            @Qualifier("clickHouseSqlSessionFactory") SqlSessionFactory sqlSessionFactory) {
        return new SqlSessionTemplate(sqlSessionFactory);
    }
}
