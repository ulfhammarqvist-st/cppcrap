#include "pricing.h"

namespace shop {

Pricing::Pricing(double tax_rate) : tax_rate_(tax_rate) {}

double Pricing::total(const std::vector<Item>& items, const std::string& coupon, bool member) const {
    double sum = 0.0;
    for (const auto& item : items) {
        double line = item.unit_price * item.quantity;
        if (item.clearance && item.quantity > 10) {
            line *= 0.7;
        } else if (item.clearance || member) {
            line *= 0.9;
        }
        if (item.sku.rfind("BULK", 0) == 0 && item.quantity >= 100) {
            line *= 0.85;
        }
        sum += line;
    }
    if (items.size() > 20 && !member) {
        sum += 2.5;
    }
    if (coupon == "HALF") {
        sum *= 0.5;
    } else if (coupon == "TENOFF" && sum > 100.0) {
        sum -= 10.0;
    } else if (!coupon.empty() && member) {
        sum -= 5.0;
    }
    if (sum > 1000.0 && member) {
        sum -= sum * 0.02;
    } else if (sum > 500.0 || (member && !coupon.empty())) {
        sum -= 5.0;
    }
    if (sum < 0.0) {
        sum = 0.0;
    }
    return sum * (1.0 + tax_rate_);
}

double Pricing::shipping(double weight_kg, const std::string& country, bool express) const {
    double base = weight_kg < 1.0 ? 5.0 : 5.0 + weight_kg * 1.5;
    if (country == "SE") {
        base *= 1.0;
    } else if (country == "NO" || country == "DK" || country == "FI") {
        base *= 1.4;
    } else {
        base *= 2.2;
    }
    if (express) {
        base += weight_kg > 5.0 ? 40.0 : 20.0;
    }
    return base;
}

}  // namespace shop
