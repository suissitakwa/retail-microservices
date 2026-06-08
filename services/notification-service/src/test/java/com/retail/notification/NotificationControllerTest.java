package com.retail.notification;

import com.retail.notification.controller.NotificationController;
import com.retail.notification.jwt.JwtService;
import com.retail.notification.response.NotificationResponse;
import com.retail.notification.service.NotificationService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.autoconfigure.security.servlet.SecurityAutoConfiguration;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import java.time.LocalDateTime;
import java.util.List;

import static org.mockito.Mockito.doNothing;
import static org.mockito.Mockito.when;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.authentication;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.patch;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(
        value = NotificationController.class,
        excludeAutoConfiguration = SecurityAutoConfiguration.class
)
class NotificationControllerTest {

    @Autowired MockMvc mockMvc;

    @MockitoBean NotificationService notificationService;
    @MockitoBean JwtService jwtService; // JwtAuthenticationFilter is a @Component picked up by the slice

    // ── helpers ──────────────────────────────────────────────────────────────

    private static Authentication customerAuth(Integer customerId) {
        var auth = new UsernamePasswordAuthenticationToken(
                "user@test.com", null,
                List.of(new SimpleGrantedAuthority("ROLE_CUSTOMER"))
        );
        auth.setDetails(customerId);
        return auth;
    }

    private static NotificationResponse sampleNotification() {
        return new NotificationResponse(1, "ORDER_PLACED", "Your order has been placed",
                false, 10, "REF-001", LocalDateTime.now());
    }

    // ── GET /my ───────────────────────────────────────────────────────────────

    @Test
    void getMyNotifications_returnsListForAuthenticatedCustomer() throws Exception {
        when(notificationService.getMyNotifications(42))
                .thenReturn(List.of(sampleNotification()));

        mockMvc.perform(get("/api/v1/notifications/my")
                        .with(authentication(customerAuth(42))))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.length()").value(1))
                .andExpect(jsonPath("$[0].type").value("ORDER_PLACED"))
                .andExpect(jsonPath("$[0].orderId").value(10))
                .andExpect(jsonPath("$[0].orderReference").value("REF-001"));
    }

    @Test
    void getMyNotifications_returnsEmptyList_whenNoNotifications() throws Exception {
        when(notificationService.getMyNotifications(42)).thenReturn(List.of());

        mockMvc.perform(get("/api/v1/notifications/my")
                        .with(authentication(customerAuth(42))))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.length()").value(0));
    }

    // ── GET /unread-count ────────────────────────────────────────────────────

    @Test
    void getUnreadCount_returnsCountForCustomer() throws Exception {
        when(notificationService.getUnreadCount(42)).thenReturn(3L);

        mockMvc.perform(get("/api/v1/notifications/unread-count")
                        .with(authentication(customerAuth(42))))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.count").value(3));
    }

    @Test
    void getUnreadCount_returnsZero_whenAllRead() throws Exception {
        when(notificationService.getUnreadCount(42)).thenReturn(0L);

        mockMvc.perform(get("/api/v1/notifications/unread-count")
                        .with(authentication(customerAuth(42))))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.count").value(0));
    }

    // ── PATCH /{id}/read ──────────────────────────────────────────────────────

    @Test
    void markAsRead_returns200_whenSuccessful() throws Exception {
        doNothing().when(notificationService).markAsRead(1, 42);

        mockMvc.perform(patch("/api/v1/notifications/1/read")
                        .with(authentication(customerAuth(42))))
                .andExpect(status().isOk());
    }
}
