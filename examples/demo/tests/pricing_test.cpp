#include "pricing.h"

#include <cassert>
#include <cmath>

using shop::Item;
using shop::Pricing;

static bool close(double a, double b) { return std::fabs(a - b) < 1e-9; }

int main() {
    Pricing pricing(0.25);
    assert(close(pricing.tax_rate(), 0.25));

    std::vector<Item> items{{"REG-1", 2, 10.0, false}};
    assert(close(pricing.total(items, "", false), 25.0));

    assert(close(pricing.shipping(0.5, "SE", false), 5.0));
    return 0;
}
