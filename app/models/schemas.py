from pydantic import BaseModel, EmailStr
from typing import Optional, List

class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str
    phone: Optional[str] = None
    role: str = "customer"          

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class VenueLocation(BaseModel):
    address: str
    city: str
    area: str
    latitude: float
    longitude: float

class VenuePricing(BaseModel):
    base_per_day: int
    advance_percent: int = 30
    peak_multiplier: float = 1.5

class VenueCapacity(BaseModel):
    min: int
    max: int

class CreateVenueRequest(BaseModel):
    name: str
    description: str
    type: str                       
    location: VenueLocation
    capacity: VenueCapacity
    pricing: VenuePricing
    services: List[str] = []
    facilities: List[str] = []

class CreateBookingRequest(BaseModel):
    venue_id: str
    event_date: str                 
    event_time: Optional[str] = None
    event_type: str
    guest_count: int
    services_requested: List[str] = []
    notes: Optional[str] = None
    bid_id: Optional[str] = None

class BookingActionRequest(BaseModel):
    action: str                     

class PaymentRequest(BaseModel):
    booking_id: str
    amount: int
    gateway: str                    
    gateway_ref: str


class CreateBidRequest(BaseModel):
    venue_ids: List[str]
    event_date: str
    event_type: str
    guest_count: int
    budget: int
    services_required: List[str] = []
    message: Optional[str] = None

class SendQuotationRequest(BaseModel):
    amount: int
    discount_percent: float = 0
    message: str
    valid_until: str
    package_details: Optional[str] = None

class BidActionRequest(BaseModel):
    action: str                     
    quotation_id: Optional[str] = None


class SendMessageRequest(BaseModel):
    room_id: str                    
    receiver_id: str
    content: str
    type: str = "text"              

class UpdateProfileRequest(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    profile_photo: Optional[str] = None



class ForgotPasswordRequest(BaseModel):
    email: str

class VerifyOtpRequest(BaseModel):
    email: str
    otp: str

class ResetPasswordRequest(BaseModel):
    email: str
    otp: str
    new_password: str