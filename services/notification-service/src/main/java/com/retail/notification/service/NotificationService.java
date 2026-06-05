package com.retail.notification.service;

import com.retail.notification.entity.Notification;
import com.retail.notification.repository.NotificationRepository;
import com.retail.notification.response.NotificationResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

import java.util.List;

@Service
@RequiredArgsConstructor
public class NotificationService {

    private final NotificationRepository notificationRepository;

    public List<NotificationResponse> getMyNotifications(Integer customerId) {
        return notificationRepository
                .findByCustomerIdOrderByCreatedDateDesc(customerId)
                .stream().map(this::toResponse).toList();
    }

    public long getUnreadCount(Integer customerId) {
        return notificationRepository.countByCustomerIdAndIsReadFalse(customerId);
    }

    public void markAsRead(Integer notificationId, Integer customerId) {
        Notification n = notificationRepository.findById(notificationId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Notification not found"));
        if (!n.getCustomerId().equals(customerId)) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "Unauthorized");
        }
        n.setRead(true);
        notificationRepository.save(n);
    }

    private NotificationResponse toResponse(Notification n) {
        return new NotificationResponse(n.getId(), n.getType(), n.getMessage(),
                n.isRead(), n.getOrderId(), n.getOrderReference(), n.getCreatedDate());
    }
}
