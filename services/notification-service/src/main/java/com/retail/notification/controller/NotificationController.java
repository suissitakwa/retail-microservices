package com.retail.notification.controller;

import com.retail.notification.response.NotificationResponse;
import com.retail.notification.service.NotificationService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/v1/notifications")
@RequiredArgsConstructor
public class NotificationController {

    private final NotificationService notificationService;

    @GetMapping("/my")
    public List<NotificationResponse> getMyNotifications(Authentication auth) {
        return notificationService.getMyNotifications(customerId(auth));
    }

    @GetMapping("/unread-count")
    public ResponseEntity<Map<String, Long>> getUnreadCount(Authentication auth) {
        return ResponseEntity.ok(Map.of("count", notificationService.getUnreadCount(customerId(auth))));
    }

    @PatchMapping("/{id}/read")
    public ResponseEntity<Void> markAsRead(@PathVariable Integer id, Authentication auth) {
        notificationService.markAsRead(id, customerId(auth));
        return ResponseEntity.ok().build();
    }

    private Integer customerId(Authentication auth) {
        return (Integer) auth.getDetails();
    }
}
