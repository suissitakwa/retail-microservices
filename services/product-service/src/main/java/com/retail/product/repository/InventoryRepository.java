package com.retail.product.repository;

import com.retail.product.entity.Inventory;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.Optional;

public interface InventoryRepository extends JpaRepository<Inventory, Integer> {

    Optional<Inventory> findByProductId(Integer productId);

    @Modifying
    @Query("UPDATE Inventory i SET i.quantity = i.quantity - :qty, i.lastUpdated = CURRENT_TIMESTAMP " +
           "WHERE i.product.id = :productId AND i.quantity >= :qty")
    int decrementStock(@Param("productId") Integer productId, @Param("qty") Integer qty);
}
