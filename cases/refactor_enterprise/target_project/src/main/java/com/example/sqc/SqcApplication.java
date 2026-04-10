package com.example.sqc;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableAsync;
import org.springframework.scheduling.annotation.EnableScheduling;

/**
 * 医疗检验质控系统启动类
 *
 * @author sqc-team
 * @since 2024-01-01
 */
@SpringBootApplication
@EnableAsync
@EnableScheduling
public class SqcApplication {

    public static void main(String[] args) {
        SpringApplication.run(SqcApplication.class, args);
    }
}
