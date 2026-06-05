package com.retail.notification.repository;

import com.retail.notification.entity.Notification;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface NotificationRepository extends JpaRepository<Notification, Integer> {
    List<Notification> findByCustomerIdOrderByCreatedDateDesc(Integer customerId);
    long countByCustomerIdAndIsReadFalse(Integer customerId);
}
