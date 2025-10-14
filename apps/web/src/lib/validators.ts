/**
 * Custom validation functions
 */

/**
 * Validate CPF
 */
export function validateCPF(cpf: string): boolean {
  if (!cpf) return false;
  
  // Remove all non-numeric characters
  const numbers = cpf.replace(/\D/g, '');
  
  // Check if it has 11 digits
  if (numbers.length !== 11) return false;
  
  // Check if all digits are the same
  if (/^(\d)\1{10}$/.test(numbers)) return false;
  
  // Validate first check digit
  let sum = 0;
  for (let i = 0; i < 9; i++) {
    sum += parseInt(numbers.charAt(i)) * (10 - i);
  }
  let remainder = (sum * 10) % 11;
  if (remainder === 10 || remainder === 11) remainder = 0;
  if (remainder !== parseInt(numbers.charAt(9))) return false;
  
  // Validate second check digit
  sum = 0;
  for (let i = 0; i < 10; i++) {
    sum += parseInt(numbers.charAt(i)) * (11 - i);
  }
  remainder = (sum * 10) % 11;
  if (remainder === 10 || remainder === 11) remainder = 0;
  if (remainder !== parseInt(numbers.charAt(10))) return false;
  
  return true;
}

/**
 * Validate CNPJ
 */
export function validateCNPJ(cnpj: string): boolean {
  if (!cnpj) return false;
  
  // Remove all non-numeric characters
  const numbers = cnpj.replace(/\D/g, '');
  
  // Check if it has 14 digits
  if (numbers.length !== 14) return false;
  
  // Check if all digits are the same
  if (/^(\d)\1{13}$/.test(numbers)) return false;
  
  // Validate first check digit
  let sum = 0;
  let weight = 2;
  for (let i = 11; i >= 0; i--) {
    sum += parseInt(numbers.charAt(i)) * weight;
    weight = weight === 9 ? 2 : weight + 1;
  }
  let remainder = sum % 11;
  const firstDigit = remainder < 2 ? 0 : 11 - remainder;
  if (firstDigit !== parseInt(numbers.charAt(12))) return false;
  
  // Validate second check digit
  sum = 0;
  weight = 2;
  for (let i = 12; i >= 0; i--) {
    sum += parseInt(numbers.charAt(i)) * weight;
    weight = weight === 9 ? 2 : weight + 1;
  }
  remainder = sum % 11;
  const secondDigit = remainder < 2 ? 0 : 11 - remainder;
  if (secondDigit !== parseInt(numbers.charAt(13))) return false;
  
  return true;
}

/**
 * Validate email
 */
export function validateEmail(email: string): boolean {
  if (!email) return false;
  
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return emailRegex.test(email);
}

/**
 * Validate phone number (Brazilian format)
 */
export function validatePhone(phone: string): boolean {
  if (!phone) return false;
  
  // Remove all non-numeric characters
  const numbers = phone.replace(/\D/g, '');
  
  // Check if it has 10 or 11 digits (landline or mobile)
  return numbers.length === 10 || numbers.length === 11;
}

/**
 * Validate CEP (Brazilian postal code)
 */
export function validateCEP(cep: string): boolean {
  if (!cep) return false;
  
  // Remove all non-numeric characters
  const numbers = cep.replace(/\D/g, '');
  
  // Check if it has 8 digits
  return numbers.length === 8;
}

/**
 * Validate required field
 */
export function validateRequired(value: any): boolean {
  if (value === null || value === undefined) return false;
  if (typeof value === 'string') return value.trim().length > 0;
  if (typeof value === 'number') return !isNaN(value);
  if (Array.isArray(value)) return value.length > 0;
  return true;
}

/**
 * Validate minimum length
 */
export function validateMinLength(value: string, minLength: number): boolean {
  if (!value) return false;
  return value.trim().length >= minLength;
}

/**
 * Validate maximum length
 */
export function validateMaxLength(value: string, maxLength: number): boolean {
  if (!value) return true;
  return value.trim().length <= maxLength;
}

/**
 * Validate numeric range
 */
export function validateRange(value: number, min: number, max: number): boolean {
  if (typeof value !== 'number' || isNaN(value)) return false;
  return value >= min && value <= max;
}

/**
 * Validate positive number
 */
export function validatePositive(value: number): boolean {
  if (typeof value !== 'number' || isNaN(value)) return false;
  return value > 0;
}

/**
 * Validate non-negative number
 */
export function validateNonNegative(value: number): boolean {
  if (typeof value !== 'number' || isNaN(value)) return false;
  return value >= 0;
}

/**
 * Validate date is not in the future
 */
export function validateDateNotFuture(date: Date | string): boolean {
  if (!date) return false;
  
  const dateObj = typeof date === 'string' ? new Date(date) : date;
  const today = new Date();
  today.setHours(23, 59, 59, 999); // End of today
  
  return dateObj <= today;
}

/**
 * Validate date is not in the past
 */
export function validateDateNotPast(date: Date | string): boolean {
  if (!date) return false;
  
  const dateObj = typeof date === 'string' ? new Date(date) : date;
  const today = new Date();
  today.setHours(0, 0, 0, 0); // Start of today
  
  return dateObj >= today;
}

/**
 * Validate minimum age
 */
export function validateMinimumAge(birthDate: Date | string, minimumAge: number): boolean {
  if (!birthDate) return false;
  
  const birth = typeof birthDate === 'string' ? new Date(birthDate) : birthDate;
  const today = new Date();
  const age = today.getFullYear() - birth.getFullYear();
  const monthDiff = today.getMonth() - birth.getMonth();
  
  if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < birth.getDate())) {
    return age - 1 >= minimumAge;
  }
  
  return age >= minimumAge;
}

/**
 * Validate file type
 */
export function validateFileType(file: File, allowedTypes: string[]): boolean {
  if (!file || !allowedTypes.length) return false;
  
  return allowedTypes.some(type => {
    if (type.includes('*')) {
      // Wildcard type (e.g., "image/*")
      const baseType = type.split('/')[0];
      return file.type.startsWith(baseType);
    } else {
      // Exact type
      return file.type === type;
    }
  });
}

/**
 * Validate file size
 */
export function validateFileSize(file: File, maxSizeInMB: number): boolean {
  if (!file) return false;
  
  const maxSizeInBytes = maxSizeInMB * 1024 * 1024;
  return file.size <= maxSizeInBytes;
}

/**
 * Validate password strength
 */
export function validatePasswordStrength(password: string): {
  isValid: boolean;
  score: number;
  feedback: string[];
} {
  if (!password) {
    return {
      isValid: false,
      score: 0,
      feedback: ['Senha é obrigatória'],
    };
  }
  
  const feedback: string[] = [];
  let score = 0;
  
  // Length check
  if (password.length >= 8) {
    score += 1;
  } else {
    feedback.push('Senha deve ter pelo menos 8 caracteres');
  }
  
  // Uppercase check
  if (/[A-Z]/.test(password)) {
    score += 1;
  } else {
    feedback.push('Senha deve conter pelo menos uma letra maiúscula');
  }
  
  // Lowercase check
  if (/[a-z]/.test(password)) {
    score += 1;
  } else {
    feedback.push('Senha deve conter pelo menos uma letra minúscula');
  }
  
  // Number check
  if (/\d/.test(password)) {
    score += 1;
  } else {
    feedback.push('Senha deve conter pelo menos um número');
  }
  
  // Special character check
  if (/[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]/.test(password)) {
    score += 1;
  } else {
    feedback.push('Senha deve conter pelo menos um caractere especial');
  }
  
  return {
    isValid: score >= 4,
    score,
    feedback: feedback.length === 0 ? ['Senha forte'] : feedback,
  };
}

/**
 * Validate URL
 */
export function validateURL(url: string): boolean {
  if (!url) return false;
  
  try {
    new URL(url);
    return true;
  } catch {
    return false;
  }
}

/**
 * Validate Brazilian license plate (new format: ABC-1234 or old format: ABC1234)
 */
export function validateLicensePlate(plate: string): boolean {
  if (!plate) return false;
  
  // Remove all non-alphanumeric characters and convert to uppercase
  const cleanPlate = plate.replace(/[^a-zA-Z0-9]/g, '').toUpperCase();
  
  // Check new format (ABC1234) or old format (ABC1234)
  const newFormatRegex = /^[A-Z]{3}[0-9][A-Z][0-9]{2}$/;
  const oldFormatRegex = /^[A-Z]{3}[0-9]{4}$/;
  
  return newFormatRegex.test(cleanPlate) || oldFormatRegex.test(cleanPlate);
}

/**
 * Validate credit card number (basic Luhn algorithm)
 */
export function validateCreditCard(cardNumber: string): boolean {
  if (!cardNumber) return false;
  
  // Remove all non-numeric characters
  const numbers = cardNumber.replace(/\D/g, '');
  
  // Check if it has 13-19 digits
  if (numbers.length < 13 || numbers.length > 19) return false;
  
  // Luhn algorithm
  let sum = 0;
  let isEven = false;
  
  for (let i = numbers.length - 1; i >= 0; i--) {
    let digit = parseInt(numbers.charAt(i));
    
    if (isEven) {
      digit *= 2;
      if (digit > 9) {
        digit -= 9;
      }
    }
    
    sum += digit;
    isEven = !isEven;
  }
  
  return sum % 10 === 0;
}

/**
 * Validate IBAN (International Bank Account Number)
 */
export function validateIBAN(iban: string): boolean {
  if (!iban) return false;
  
  // Remove spaces and convert to uppercase
  const cleanIban = iban.replace(/\s/g, '').toUpperCase();
  
  // Check if it starts with "BR" and has correct length (29 characters)
  if (!cleanIban.startsWith('BR') || cleanIban.length !== 29) return false;
  
  // Move first 4 characters to end
  const rearranged = cleanIban.slice(4) + cleanIban.slice(0, 4);
  
  // Replace letters with numbers (A=10, B=11, etc.)
  const numericString = rearranged.replace(/[A-Z]/g, (char) => 
    (char.charCodeAt(0) - 55).toString()
  );
  
  // Calculate mod 97
  let remainder = 0;
  for (let i = 0; i < numericString.length; i++) {
    remainder = (remainder * 10 + parseInt(numericString.charAt(i))) % 97;
  }
  
  return remainder === 1;
}

/**
 * Create a custom validator function
 */
export function createValidator<T>(
  validateFn: (value: T) => boolean,
  errorMessage: string
): (value: T) => string | null {
  return (value: T) => {
    return validateFn(value) ? null : errorMessage;
  };
}

/**
 * Combine multiple validators
 */
export function combineValidators<T>(
  validators: Array<(value: T) => string | null>
): (value: T) => string | null {
  return (value: T) => {
    for (const validator of validators) {
      const error = validator(value);
      if (error) return error;
    }
    return null;
  };
}
