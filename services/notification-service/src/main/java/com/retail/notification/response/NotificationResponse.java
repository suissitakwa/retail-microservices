package com.retail.notification.response;

import java.time.LocalDateTime;

public record NotificationResponse(
        Integer id,
        String type,
        String message,
        boolean isRead,
        Integer orderId,
        String orderReference,
        LocalDateTime createdDate
) {}
