package com.retail.customer.jwt;

import com.retail.customer.entity.Customer;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.userdetails.UserDetails;

import java.util.Collection;
import java.util.List;

public class MyUserDetails implements UserDetails {

    private final Customer customer;

    public MyUserDetails(Customer customer) {
        this.customer = customer;
    }

    public Customer getCustomer() { return customer; }

    @Override
    public Collection<? extends GrantedAuthority> getAuthorities() {
        return List.of(new SimpleGrantedAuthority(customer.getRole().name()));
    }

    @Override public String getPassword()  { return customer.getPassword(); }
    @Override public String getUsername()  { return customer.getEmail(); }
    @Override public boolean isAccountNonExpired()     { return true; }
    @Override public boolean isAccountNonLocked()      { return true; }
    @Override public boolean isCredentialsNonExpired() { return true; }
    @Override public boolean isEnabled()               { return true; }
}
