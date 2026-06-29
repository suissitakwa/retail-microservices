package com.retail.customer.email;

import jakarta.mail.MessagingException;
import jakarta.mail.internet.MimeMessage;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.mail.javamail.JavaMailSender;
import org.springframework.mail.javamail.MimeMessageHelper;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;

@Service
@RequiredArgsConstructor
@Slf4j
public class EmailService {

    private final JavaMailSender mailSender;

    @Async
    public void sendPasswordReset(String toEmail, String firstName, String resetLink) {
        try {
            MimeMessage message = mailSender.createMimeMessage();
            MimeMessageHelper helper = new MimeMessageHelper(message, true, "UTF-8");
            helper.setTo(toEmail);
            helper.setSubject("Reset your NovaMart password");
            helper.setText(buildHtml(firstName, resetLink), true);
            mailSender.send(message);
            log.info("Password reset email sent to {}", toEmail);
        } catch (MessagingException e) {
            log.warn("Failed to send password reset email to {}: {}", toEmail, e.getMessage());
        }
    }

    private String buildHtml(String firstName, String resetLink) {
        return """
                <!DOCTYPE html>
                <html>
                <body style="font-family:Arial,sans-serif;background:#f4f4f4;margin:0;padding:20px;">
                  <div style="max-width:600px;margin:0 auto;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.1);">
                    <div style="background:#1a1a2e;padding:30px;text-align:center;">
                      <h1 style="color:#f5c518;margin:0;font-size:24px;">NovaMart</h1>
                    </div>
                    <div style="padding:30px;">
                      <h2 style="color:#333;margin-top:0;">Hi %s, reset your password</h2>
                      <p style="color:#555;">We received a request to reset your password. Click the button below — this link expires in 1 hour.</p>
                      <div style="text-align:center;margin:30px 0;">
                        <a href="%s"
                           style="background:#f5c518;color:#1a1a2e;padding:12px 28px;border-radius:6px;text-decoration:none;font-weight:bold;">
                          Reset Password
                        </a>
                      </div>
                      <p style="color:#999;font-size:13px;">If you didn't request this, you can safely ignore this email.</p>
                    </div>
                    <div style="background:#f4f4f4;padding:16px;text-align:center;">
                      <p style="color:#999;font-size:12px;margin:0;">© 2025 NovaMart</p>
                    </div>
                  </div>
                </body>
                </html>
                """.formatted(firstName, resetLink);
    }
}
