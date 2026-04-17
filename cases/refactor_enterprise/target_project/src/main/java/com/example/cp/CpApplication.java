package com.example.cp;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableAsync;
import org.springframework.scheduling.annotation.EnableScheduling;

/**
 * 医疗诊疗临床路径系统启动类
 *
 * @author cp-team
 * @since 2024-01-01
 */
@SpringBootApplication
@EnableAsync
@EnableScheduling
public class CpApplication {

    public static void main(String[] args) {
        SpringApplication.run(CpApplication.class, args);
    }
}
