#pragma once

#include <string>
#include <vector>

namespace shop {

struct Item {
    std::string sku;
    int quantity;
    double unit_price;
    bool clearance;
};

class Pricing {
public:
    explicit Pricing(double tax_rate);

    double total(const std::vector<Item>& items, const std::string& coupon, bool member) const;
    double shipping(double weight_kg, const std::string& country, bool express) const;
    double tax_rate() const { return tax_rate_; }

private:
    double tax_rate_;
};

}  // namespace shop
