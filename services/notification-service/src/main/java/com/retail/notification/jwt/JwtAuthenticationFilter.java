package com.retail.notification.jwt;

import io.jsonwebtoken.Claims;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.util.List;

@Component
@RequiredArgsConstructor
public class JwtAuthenticationFilter extends OncePerRequestFilter {

    private final JwtService jwtService;

    @Override
    protected void doFilterInternal(HttpServletRequest request,
                                    HttpServletResponse response,
                                    FilterChain chain)
            throws ServletException, IOException {

        String header = request.getHeader("Authorization");
        if (header == null || !header.startsWith("Bearer ")) { chain.doFilter(request, response); return; }

        String token = header.substring(7);
        if (!jwtService.isTokenValid(token)) { chain.doFilter(request, response); return; }

        Claims claims     = jwtService.getClaims(token);
        String email      = claims.getSubject();
        Integer customerId = claims.get("customerId", Integer.class);
        String role       = extractRole(claims.get("role"));

        if (email != null && SecurityContextHolder.getContext().getAuthentication() == null) {
            List<SimpleGrantedAuthority> authorities =
                    role != null ? List.of(new SimpleGrantedAuthority(role)) : List.of();
            var auth = new UsernamePasswordAuthenticationToken(email, null, authorities);
            auth.setDetails(customerId);
            SecurityContextHolder.getContext().setAuthentication(auth);
        }
        chain.doFilter(request, response);
    }

    private String extractRole(Object roleObj) {
        if (roleObj == null) return null;
        if (roleObj instanceof List<?> list && !list.isEmpty()) {
            Object first = list.get(0);
            if (first instanceof java.util.Map<?,?> map) { Object a = map.get("authority"); return a != null ? a.toString() : null; }
            return first.toString();
        }
        return roleObj.toString();
    }
}
