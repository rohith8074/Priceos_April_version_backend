from typing import List, Optional, Dict, Any
from datetime import datetime, date

class OccupancyWindowProfile:
    def __init__(self, startDay: int, endDay: int, highThresholdPct: float, highAdjPct: float, lowThresholdPct: float, lowAdjPct: float):
        self.startDay = startDay
        self.endDay = endDay
        self.highThresholdPct = highThresholdPct
        self.highAdjPct = highAdjPct
        self.lowThresholdPct = lowThresholdPct
        self.lowAdjPct = lowAdjPct

class ListingConfig:
    def __init__(self, **kwargs):
        self.basePrice = kwargs.get('basePrice', 0.0)
        self.basePriceWeekend = kwargs.get('basePriceWeekend', 0.0)
        self.absoluteMinPrice = kwargs.get('absoluteMinPrice', 0.0)
        self.absoluteMaxPrice = kwargs.get('absoluteMaxPrice', 0.0)
        self.defaultMinStay = kwargs.get('defaultMinStay', 1)
        self.defaultMaxStay = kwargs.get('defaultMaxStay', 365)
        self.lowestMinStayAllowed = kwargs.get('lowestMinStayAllowed', 1)
        self.allowedCheckinDays = kwargs.get('allowedCheckinDays', [1]*7) # [Mon..Sun]
        self.allowedCheckoutDays = kwargs.get('allowedCheckoutDays', [1]*7) # [Mon..Sun]

        self.lastMinuteEnabled = kwargs.get('lastMinuteEnabled', False)
        self.lastMinuteDaysOut = kwargs.get('lastMinuteDaysOut', 7)
        self.lastMinuteDiscountPct = kwargs.get('lastMinuteDiscountPct', 15)
        self.lastMinuteMinStay = kwargs.get('lastMinuteMinStay')

        self.lastMinuteRampEnabled = kwargs.get('lastMinuteRampEnabled', False)
        self.lastMinuteRampDays = kwargs.get('lastMinuteRampDays', 15)
        self.lastMinuteMaxDiscountPct = kwargs.get('lastMinuteMaxDiscountPct', 30)
        self.lastMinuteMinDiscountPct = kwargs.get('lastMinuteMinDiscountPct', 5)

        self.farOutEnabled = kwargs.get('farOutEnabled', False)
        self.farOutDaysOut = kwargs.get('farOutDaysOut', 90)
        self.farOutMarkupPct = kwargs.get('farOutMarkupPct', 10)
        self.farOutMinStay = kwargs.get('farOutMinStay')
        self.farOutMinPrice = kwargs.get('farOutMinPrice', 0.0)

        self.dowPricingEnabled = kwargs.get('dowPricingEnabled', False)
        self.dowDays = kwargs.get('dowDays', [4, 5])
        self.dowPriceAdjPct = kwargs.get('dowPriceAdjPct', 20)
        self.dowMinStay = kwargs.get('dowMinStay')

        self.gapPreventionEnabled = kwargs.get('gapPreventionEnabled', True)
        self.minFragmentThreshold = kwargs.get('minFragmentThreshold', 3)

        self.gapFillEnabled = kwargs.get('gapFillEnabled', False)
        self.gapFillLengthMin = kwargs.get('gapFillLengthMin', 1)
        self.gapFillLengthMax = kwargs.get('gapFillLengthMax', 3)
        self.gapFillDiscountPct = kwargs.get('gapFillDiscountPct', 10)
        self.gapFillDiscountWeekdayPct = kwargs.get('gapFillDiscountWeekdayPct', 0)
        self.gapFillDiscountWeekendPct = kwargs.get('gapFillDiscountWeekendPct', 0)
        self.gapFillMaxDaysUntilCheckin = kwargs.get('gapFillMaxDaysUntilCheckin', 30)
        self.gapFillOverrideCico = kwargs.get('gapFillOverrideCico', True)
        
        self.adjacentAdjustmentEnabled = kwargs.get('adjacentAdjustmentEnabled', False)
        self.adjacentAdjustmentPct = kwargs.get('adjacentAdjustmentPct', 0)
        self.adjacentTurnoverCost = kwargs.get('adjacentTurnoverCost', 0)

        self.occupancyEnabled = kwargs.get('occupancyEnabled', False)
        self.currentOccupancyPct = kwargs.get('currentOccupancyPct', 0)
        self.occupancyTargetPct = kwargs.get('occupancyTargetPct', 75)
        self.occupancyHighThresholdPct = kwargs.get('occupancyHighThresholdPct', 85)
        self.occupancyHighAdjPct = kwargs.get('occupancyHighAdjPct', 15)
        self.occupancyLowThresholdPct = kwargs.get('occupancyLowThresholdPct', 50)
        self.occupancyLowAdjPct = kwargs.get('occupancyLowAdjPct', -10)
        
        self.occupancyWindowProfiles: List[OccupancyWindowProfile] = []
        for p in kwargs.get('occupancyWindowProfiles', []):
            if isinstance(p, dict):
                self.occupancyWindowProfiles.append(OccupancyWindowProfile(**p))

        self.weekendMinPrice = kwargs.get('weekendMinPrice', 0)
        self.weekendDays = kwargs.get('weekendDays', [4, 5])
        self.marketPacingAdjPct = kwargs.get('marketPacingAdjPct', 0)

class Rule:
    def __init__(self, **kwargs):
        self.id = kwargs.get('id')
        self.ruleType = kwargs.get('ruleType')
        self.name = kwargs.get('name', '')
        self.enabled = kwargs.get('enabled', True)
        self.priority = kwargs.get('priority', 0)
        self.startDate = kwargs.get('startDate')
        self.endDate = kwargs.get('endDate')
        self.daysOfWeek = kwargs.get('daysOfWeek')
        self.minNights = kwargs.get('minNights')
        self.priceOverride = kwargs.get('priceOverride')
        self.priceAdjPct = kwargs.get('priceAdjPct')
        self.minPriceOverride = kwargs.get('minPriceOverride')
        self.maxPriceOverride = kwargs.get('maxPriceOverride')
        self.minStayOverride = kwargs.get('minStayOverride')
        self.isBlocked = kwargs.get('isBlocked', False)
        self.closedToArrival = kwargs.get('closedToArrival', False)
        self.closedToDeparture = kwargs.get('closedToDeparture', False)
        self.suspendLastMinute = kwargs.get('suspendLastMinute', False)
        self.suspendGapFill = kwargs.get('suspendGapFill', False)

class BookingContext:
    def __init__(self, **kwargs):
        self.isBooked = kwargs.get('isBooked', False)
        self.gapLength = kwargs.get('gapLength')
        self.gapStart = kwargs.get('gapStart')
        self.gapEnd = kwargs.get('gapEnd')
        self.adjacentToBooking = kwargs.get('adjacentToBooking', False)

class DayResult:
    def __init__(self, price: float, minimumStay: int, maximumStay: int, isAvailable: int, closedToArrival: int, closedToDeparture: int, note: str):
        self.price = price
        self.minimumStay = minimumStay
        self.maximumStay = maximumStay
        self.isAvailable = isAvailable
        self.closedToArrival = closedToArrival
        self.closedToDeparture = closedToDeparture
        self.note = note

def get_dow(dt: date) -> int:
    return dt.weekday()

def days_between(a: date, b: date) -> int:
    return (b - a).days

def date_str(dt: date) -> str:
    return dt.isoformat()

def compute_day(target_date: date, today: date, config: ListingConfig, all_rules: List[Rule], booking_ctx: BookingContext) -> DayResult:
    notes: List[str] = []
    dow = get_dow(target_date)
    lead_time = days_between(today, target_date)

    is_weekend_day = dow in config.weekendDays
    effective_base = config.basePriceWeekend if (is_weekend_day and config.basePriceWeekend > 0) else config.basePrice

    price = float(effective_base)
    minimum_stay = config.defaultMinStay
    maximum_stay = config.defaultMaxStay
    is_available = 0 if booking_ctx.isBooked else 1
    closed_to_arrival = 1 if config.allowedCheckinDays[dow] == 0 else 0
    closed_to_departure = 1 if config.allowedCheckoutDays[dow] == 0 else 0

    if closed_to_arrival: notes.append("[BASE] Closed to arrival (DOW restriction)")
    if closed_to_departure: notes.append("[BASE] Closed to departure (DOW restriction)")

    suspend_last_minute = False
    suspend_gap_fill = False
    rule_min_price = None
    rule_max_price = None

    valid_rules = []
    ds = date_str(target_date)
    for r in all_rules:
        if not r.enabled: continue
        if r.ruleType not in ["SEASON", "EVENT", "ADMIN_BLOCK"]: continue
        if not r.startDate or not r.endDate: continue
        if ds < r.startDate or ds > r.endDate: continue
        if r.daysOfWeek and len(r.daysOfWeek) > 0:
            if r.daysOfWeek[dow] == 0: continue
        valid_rules.append(r)
        
    valid_rules.sort(key=lambda r: r.priority, reverse=True)

    if valid_rules:
        winner = valid_rules[0]
        if winner.priceOverride is not None:
            price = winner.priceOverride
            notes.append(f"[{winner.ruleType}] \"{winner.name}\" set price to {price}")
        elif winner.priceAdjPct is not None:
            price = price * (1 + winner.priceAdjPct / 100.0)
            notes.append(f"[{winner.ruleType}] \"{winner.name}\" adjusted price by {winner.priceAdjPct}%")

        if winner.minStayOverride is not None:
            minimum_stay = winner.minStayOverride
            notes.append(f"[{winner.ruleType}] \"{winner.name}\" set min stay to {minimum_stay}")

        if winner.isBlocked:
            is_available = 0
            notes.append(f"[{winner.ruleType}] \"{winner.name}\" blocked this day")

        if winner.closedToArrival:
            closed_to_arrival = 1
            notes.append(f"[{winner.ruleType}] \"{winner.name}\" closed to arrival")
        if winner.closedToDeparture:
            closed_to_departure = 1
            notes.append(f"[{winner.ruleType}] \"{winner.name}\" closed to departure")

        suspend_last_minute = winner.suspendLastMinute
        suspend_gap_fill = winner.suspendGapFill
        rule_min_price = winner.minPriceOverride
        rule_max_price = winner.maxPriceOverride

    if config.marketPacingAdjPct:
        price = price * (1 + config.marketPacingAdjPct / 100.0)
        notes.append(f"[AIRBTICS_PACING] Market intel adjusted price by {config.marketPacingAdjPct}%")

    if booking_ctx.isBooked:
        is_available = 0
        notes.append("[BOOKED] Day is booked")

    if config.lastMinuteEnabled and not suspend_last_minute and 0 <= lead_time <= config.lastMinuteDaysOut and is_available == 1:
        if config.lastMinuteRampEnabled and config.lastMinuteRampDays > 0:
            ramp_window = min(config.lastMinuteRampDays, config.lastMinuteDaysOut)
            t = min(lead_time / float(ramp_window), 1.0)
            discount_pct = config.lastMinuteMaxDiscountPct * (1 - t) + config.lastMinuteMinDiscountPct * t
            notes.append(f"[LAST_MINUTE_RAMP] {discount_pct:.1f}% discount")
        else:
            discount_pct = config.lastMinuteDiscountPct
            notes.append(f"[LAST_MINUTE] {discount_pct}% discount")
            
        price = price * (1 - discount_pct / 100.0)
        if config.lastMinuteMinStay is not None:
            minimum_stay = config.lastMinuteMinStay
            notes.append(f"[LAST_MINUTE] min stay override to {minimum_stay}")

    if config.farOutEnabled and not suspend_last_minute and lead_time >= config.farOutDaysOut and is_available == 1:
        price = price * (1 + config.farOutMarkupPct / 100.0)
        notes.append(f"[FAR_OUT] {config.farOutMarkupPct}% premium")
        if config.farOutMinStay is not None:
            minimum_stay = config.farOutMinStay
        if config.farOutMinPrice > 0 and price < config.farOutMinPrice:
            price = config.farOutMinPrice

    if config.dowPricingEnabled and dow in config.dowDays and is_available == 1:
        price = price * (1 + config.dowPriceAdjPct / 100.0)
        notes.append(f"[DOW] {config.dowPriceAdjPct}% adjustment for day {dow}")
        if config.dowMinStay is not None:
            minimum_stay = config.dowMinStay

    if config.occupancyEnabled and is_available == 1:
        occ = config.currentOccupancyPct
        profile = next((p for p in config.occupancyWindowProfiles if p.startDay <= lead_time <= p.endDay), None)
        high_thresh = profile.highThresholdPct if profile else config.occupancyHighThresholdPct
        low_thresh = profile.lowThresholdPct if profile else config.occupancyLowThresholdPct
        high_adj = profile.highAdjPct if profile else config.occupancyHighAdjPct
        low_adj = profile.lowAdjPct if profile else config.occupancyLowAdjPct

        if occ > high_thresh:
            price = price * (1 + high_adj / 100.0)
            notes.append(f"[OCCUPANCY] > high threshold {high_thresh}%, +{high_adj}%")
        elif occ < low_thresh:
            price = price * (1 + low_adj / 100.0)
            notes.append(f"[OCCUPANCY] < low threshold {low_thresh}%, {low_adj}%")

    los_rules = [r for r in all_rules if r.enabled and r.ruleType == "LOS_DISCOUNT" and r.minNights is not None]
    if los_rules:
        los_notes = [f"{r.minNights}+ nights: {r.priceAdjPct}%" for r in sorted(los_rules, key=lambda x: x.minNights, reverse=True)]
        notes.append(f"[LOS_DISCOUNT] Available: {', '.join(los_notes)}")

    if booking_ctx.gapLength is not None and not booking_ctx.isBooked and is_available == 1:
        if config.gapPreventionEnabled and booking_ctx.gapLength < config.minFragmentThreshold:
            is_available = 0
            notes.append(f"[GAP_PREVENTION] Gap of {booking_ctx.gapLength} days < threshold")
            
        gap_discount = config.gapFillDiscountWeekendPct if (is_weekend_day and config.gapFillDiscountWeekendPct > 0) else (config.gapFillDiscountWeekdayPct if (not is_weekend_day and config.gapFillDiscountWeekdayPct > 0) else config.gapFillDiscountPct)
        
        if config.gapFillEnabled and not suspend_gap_fill and is_available == 1 and config.gapFillLengthMin <= booking_ctx.gapLength <= config.gapFillLengthMax and lead_time <= config.gapFillMaxDaysUntilCheckin:
            price = price * (1 - gap_discount / 100.0)
            minimum_stay = booking_ctx.gapLength
            notes.append(f"[GAP_FILL] {gap_discount}% discount")
            if config.gapFillOverrideCico:
                closed_to_arrival = 0
                closed_to_departure = 0

    if config.adjacentAdjustmentEnabled and is_available == 1 and booking_ctx.adjacentToBooking:
        price = price * (1 + config.adjacentAdjustmentPct / 100.0) + config.adjacentTurnoverCost
        notes.append(f"[ADJACENT] Applied {config.adjacentAdjustmentPct}% and turnover {config.adjacentTurnoverCost}")

    if config.weekendMinPrice > 0 and dow in config.weekendDays and is_available == 1 and price < config.weekendMinPrice:
        price = config.weekendMinPrice

    effective_min_price = rule_min_price if rule_min_price is not None else config.absoluteMinPrice
    effective_max_price = rule_max_price if rule_max_price is not None else config.absoluteMaxPrice

    if price < effective_min_price:
        price = effective_min_price
    if price > effective_max_price:
        price = effective_max_price

    if minimum_stay < config.lowestMinStayAllowed:
        minimum_stay = config.lowestMinStayAllowed

    price = round(price, 2)

    return DayResult(
        price=price,
        minimumStay=minimum_stay,
        maximumStay=maximum_stay,
        isAvailable=is_available,
        closedToArrival=closed_to_arrival,
        closedToDeparture=closed_to_departure,
        note="; ".join(notes)
    )
