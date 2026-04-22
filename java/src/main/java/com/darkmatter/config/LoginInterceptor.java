package com.darkmatter.config;

import com.darkmatter.support.SessionKeys;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.servlet.http.HttpSession;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.HandlerInterceptor;

@Component
public class LoginInterceptor implements HandlerInterceptor {

    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler)
            throws Exception {
        String path = request.getRequestURI();
        String method = request.getMethod();
        if (isPublic(path, method)) {
            return true;
        }
        HttpSession session = request.getSession(false);
        if (session == null || session.getAttribute(SessionKeys.NAME) == null) {
            response.sendRedirect("/");
            return false;
        }
        return true;
    }

    private static boolean isPublic(String path, String method) {
        if (path.startsWith("/error")) {
            return true;
        }
        if (path.equals("/logout")) {
            return true;
        }
        if (path.equals("/")) {
            return "GET".equals(method) || "POST".equals(method);
        }
        return false;
    }
}
