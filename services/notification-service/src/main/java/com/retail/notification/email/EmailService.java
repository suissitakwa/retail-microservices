package com.retail.notification.email;

import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.util.List;
import java.util.Map;

@Service
@Slf4j
public class EmailService {

    private final HttpClient httpClient = HttpClient.newHttpClient();
    private final ObjectMapper objectMapper = new ObjectMapper();

    @Value("${MAIL_PASSWORD:disabled}")
    private String resendApiKey;

    @Value("${app.mail.from:NovaMart <onboarding@resend.dev>}")
    private String fromAddress;

    @Async
    public void sendOrderPlaced(String toEmail, String firstName, String orderReference, BigDecimal amount) {
        send(toEmail, "Order #" + orderReference + " placed — NovaMart",
                buildOrderPlacedHtml(firstName, orderReference, amount));
    }

    @Async
    public void sendOrderConfirmation(String toEmail, String firstName, String orderReference, BigDecimal amount) {
        send(toEmail, "Your NovaMart order is confirmed!", buildOrderConfirmedHtml(firstName, orderReference, amount));
    }

    private void send(String toEmail, String subject, String html) {
        try {
            String body = objectMapper.writeValueAsString(Map.of(
                    "from", fromAddress,
                    "to", List.of(toEmail),
                    "subject", subject,
                    "html", html
            ));
            HttpRequest request = HttpRequest.newBuilder()
                    .uri(URI.create("https://api.resend.com/emails"))
                    .header("Authorization", "Bearer " + resendApiKey)
                    .header("Content-Type", "application/json")
                    .POST(HttpRequest.BodyPublishers.ofString(body))
                    .build();
            HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
            if (response.statusCode() >= 400) {
                log.warn("Resend API error sending to {}: {} {}", toEmail, response.statusCode(), response.body());
            } else {
                log.info("Email sent to {} via Resend (status {})", toEmail, response.statusCode());
            }
        } catch (Exception e) {
            log.warn("Failed to send email to {}: {}", toEmail, e.getMessage());
        }
    }

    private String buildOrderPlacedHtml(String firstName, String orderReference, BigDecimal amount) {
        return """
                <!DOCTYPE html>
                <html>
                <body style="font-family:Arial,sans-serif;background:#f4f4f4;margin:0;padding:20px;">
                  <div style="max-width:600px;margin:0 auto;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.1);">
                    <div style="background:#1a1a2e;padding:30px;text-align:center;">
                      <h1 style="color:#f5c518;margin:0;font-size:24px;">NovaMart</h1>
                    </div>
                    <div style="padding:30px;">
                      <h2 style="color:#333;margin-top:0;">Hi %s, your order is placed!</h2>
                      <p style="color:#555;">We've received your order. Please complete payment to confirm it.</p>
                      <div style="background:#f9f9f9;border-radius:6px;padding:16px;margin:20px 0;">
                        <p style="margin:0 0 8px;"><strong>Order:</strong> #%s</p>
                        <p style="margin:8px 0 0;font-size:18px;"><strong>Total: $%s</strong></p>
                      </div>
                      <div style="text-align:center;margin:30px 0;">
                        <a href="https://retail-novamart.netlify.app/orders"
                           style="background:#f5c518;color:#1a1a2e;padding:12px 28px;border-radius:6px;text-decoration:none;font-weight:bold;">
                          View My Orders
                        </a>
                      </div>
                    </div>
                    <div style="background:#f4f4f4;padding:16px;text-align:center;">
                      <p style="color:#999;font-size:12px;margin:0;">© 2025 NovaMart</p>
                    </div>
                  </div>
                </body>
                </html>
                """.formatted(firstName, orderReference, amount.toPlainString());
    }

    private String buildOrderConfirmedHtml(String firstName, String orderReference, BigDecimal amount) {
        return """
                <!DOCTYPE html>
                <html>
                <body style="font-family:Arial,sans-serif;background:#f4f4f4;margin:0;padding:20px;">
                  <div style="max-width:600px;margin:0 auto;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.1);">
                    <div style="background:#1a1a2e;padding:30px;text-align:center;">
                      <h1 style="color:#f5c518;margin:0;font-size:24px;">NovaMart</h1>
                    </div>
                    <div style="padding:30px;">
                      <h2 style="color:#333;margin-top:0;">Hi %s, payment confirmed!</h2>
                      <p style="color:#555;">Great news — your payment has been received and your order is on its way.</p>
                      <div style="background:#f9f9f9;border-radius:6px;padding:16px;margin:20px 0;">
                        <p style="margin:0 0 8px;"><strong>Order:</strong> #%s</p>
                        <p style="margin:8px 0 0;font-size:18px;"><strong>Total: $%s</strong></p>
                      </div>
                      <div style="text-align:center;margin:30px 0;">
                        <a href="https://retail-novamart.netlify.app/orders"
                           style="background:#f5c518;color:#1a1a2e;padding:12px 28px;border-radius:6px;text-decoration:none;font-weight:bold;">
                          View My Orders
                        </a>
                      </div>
                    </div>
                    <div style="background:#f4f4f4;padding:16px;text-align:center;">
                      <p style="color:#999;font-size:12px;margin:0;">© 2025 NovaMart · You received this because you placed an order.</p>
                    </div>
                  </div>
                </body>
                </html>
                """.formatted(firstName, orderReference, amount.toPlainString());
    }
}
