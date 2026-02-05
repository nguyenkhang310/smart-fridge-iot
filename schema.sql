CREATE DATABASE IF NOT EXISTS smart_fridge 
CHARACTER SET utf8mb4 
COLLATE utf8mb4_unicode_ci;

USE smart_fridge;

CREATE TABLE IF NOT EXISTS sensors (
    id INT AUTO_INCREMENT PRIMARY KEY,
    temperature FLOAT,
    humidity FLOAT,
    target_temperature FLOAT,
    status VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS inventory (
    id INT AUTO_INCREMENT PRIMARY KEY,
    total_items INT,
    fruit_count INT,
    food_count INT,
    other_count INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS detections (
    id INT AUTO_INCREMENT PRIMARY KEY,
    class_name VARCHAR(100),
    confidence FLOAT,
    category VARCHAR(50),
    bbox_x INT,
    bbox_y INT,
    bbox_width INT,
    bbox_height INT,
    image_path VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS detection_sessions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    total_items INT,
    fruit_count INT,
    food_count INT,
    other_count INT,
    image_path VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS temperature_settings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    target_temperature FLOAT,
    previous_temperature FLOAT,
    changed_by VARCHAR(50), 
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);