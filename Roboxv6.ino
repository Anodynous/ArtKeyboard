/*********************************************************************
 This is an example for our nRF52 based Bluefruit LE modules

 Pick one up today in the adafruit shop!

 Adafruit invests time and resources providing this open source code,
 please support Adafruit and open-source hardware by purchasing
 products from Adafruit!

 MIT license, check LICENSE for more information
 All text above, and the splash screen below must be included in
 any redistribution
*********************************************************************/

/* This sketch demonstate how to use BLE HID to scan an array of pin
 * and send its keycode. It is essentially an implementation of hid keyboard,
 * useful reference if you want to make an BLE keyboard.
 */

#include <bluefruit.h>

BLEHidAdafruit blehid;

// Array of pins and its keycode
// For keycode definition see BLEHidGeneric.h
uint8_t pins[]    = {A2,11};
uint8_t hidcode[] = {HID_KEY_BRACKET_RIGHT,HID_KEY_BRACKET_LEFT};

uint8_t pincount = sizeof(pins)/sizeof(pins[0]);

// Modifier keys, only take cares of Shift
// ATL, CTRL, CMD keys are left for user excersie.
uint8_t testPin = A0;
uint8_t testPin2 = 15;
uint8_t testPin3 = 27;
uint8_t testPin4 = A3;
uint8_t testPin5 = 31;
uint8_t testPin6 = 30;
uint8_t testPin7 = 25;
uint8_t testPin8 = A5;
uint8_t testPin9 = A4;
uint8_t apple = A1;
int num = 0;
bool keyPressedPreviously = false;

void setup() 
{
  Serial.begin(115200);
  while ( !Serial ) delay(10);   // for nrf52840 with native usb

  Serial.println("Bluefruit52 HID Keyscan Example");
  Serial.println("-------------------------------\n");

  Serial.println();
  Serial.println("Go to your phone's Bluetooth settings to pair your device");
  Serial.println("then open an application that accepts keyboard input");

  Serial.println();
  Serial.println("Wire configured Pin to GND to send key");
  Serial.println("Wire Shift Keky to GND if you want to send it in upper case");
  Serial.println();  

  Bluefruit.begin();
  // Set max power. Accepted values are: -40, -30, -20, -16, -12, -8, -4, 0, 4
  Bluefruit.setTxPower(4);
  Bluefruit.setName("RoboxV4");

  // set up pin as input
  for (uint8_t i=0; i<pincount; i++)
  {
    pinMode(pins[i], INPUT_PULLUP);
  }

  // set up modifier key
  pinMode(testPin, INPUT_PULLUP);
  pinMode(testPin2, INPUT_PULLUP);
  pinMode(testPin3, INPUT_PULLUP);
  pinMode(testPin4, INPUT_PULLUP);
  pinMode(testPin5, INPUT_PULLUP);
  pinMode(testPin6, INPUT_PULLUP);
  pinMode(testPin7, INPUT_PULLUP);
  pinMode(testPin8, INPUT_PULLUP);
  pinMode(testPin9, INPUT_PULLUP);
  pinMode(apple, INPUT_PULLUP);
  /* Start BLE HID
   * Note: Apple requires BLE device must have min connection interval >= 20m
   * ( The smaller the connection interval the faster we could send data).
   * However for HID and MIDI device, Apple could accept min connection interval 
   * up to 11.25 ms. Therefore BLEHidAdafruit::begin() will try to set the min and max
   * connection interval to 11.25  ms and 15 ms respectively for best performance.
   */
  blehid.begin();

  // Set callback for set LED from central
  blehid.setKeyboardLedCallback(set_keyboard_led);

  /* Set connection interval (min, max) to your perferred value.
   * Note: It is already set by BLEHidAdafruit::begin() to 11.25ms - 15ms
   * min = 9*1.25=11.25 ms, max = 12*1.25= 15 ms 
   */
  /* Bluefruit.setConnInterval(9, 12); */

  // Set up and start advertising
  startAdv();
}

void startAdv(void)
{  
  // Advertising packet
  Bluefruit.Advertising.addFlags(BLE_GAP_ADV_FLAGS_LE_ONLY_GENERAL_DISC_MODE);
  Bluefruit.Advertising.addTxPower();
  Bluefruit.Advertising.addAppearance(BLE_APPEARANCE_HID_KEYBOARD);
  
  // Include BLE HID service
  Bluefruit.Advertising.addService(blehid);

  // There is enough room for the dev name in the advertising packet
  Bluefruit.Advertising.addName();
  
  /* Start Advertising
   * - Enable auto advertising if disconnected
   * - Interval:  fast mode = 20 ms, slow mode = 152.5 ms
   * - Timeout for fast mode is 30 seconds
   * - Start(timeout) with timeout = 0 will advertise forever (until connected)
   * 
   * For recommended advertising interval
   * https://developer.apple.com/library/content/qa/qa1931/_index.html   
   */
  Bluefruit.Advertising.restartOnDisconnect(true);
  Bluefruit.Advertising.setInterval(32, 244);    // in unit of 0.625 ms
  Bluefruit.Advertising.setFastTimeout(30);      // number of seconds in fast mode
  Bluefruit.Advertising.start(0);                // 0 = Don't stop advertising after n seconds
}

void loop()
{
  /*-------------- Scan Pin Array and send report ---------------------*/
  bool anyKeyPressed = false;

  uint8_t modifier = 0;
  uint8_t modifier2 = 0;
  uint8_t count=0;
  uint8_t keycode[6] = { 0 };
  uint8_t undo = HID_KEY_Z;
  uint8_t redo = HID_KEY_Y;
  uint8_t ce = HID_KEY_C;            // ipad
  uint8_t alt = HID_KEY_ALT_LEFT;   // win
  
  // scan modifier key (only SHIFT), user implement ATL, CTRL, CMD if needed   V4


  if ( 0 == digitalRead(apple) )
  {
   if (num == 0)
   {
   num = 1 ;
   }
   else
   {
   blehid.keyboardReport(0, HID_KEY_C);
   anyKeyPressed = true;
   keyPressedPreviously = true;  
   }
   
  }
  
  if ( 0 == digitalRead(testPin) )
  {
   if (num == 1)
   {
    modifier2 |= KEYBOARD_MODIFIER_LEFTGUI;    
   }
   else
   {
    modifier2 |= KEYBOARD_MODIFIER_LEFTCTRL;
   }
   blehid.keyboardReport(modifier2, undo);
   anyKeyPressed = true;
   keyPressedPreviously = true;
  }


  if ( 0 == digitalRead(testPin2) )
  {
   if (num == 1)
   {
    modifier2 |= KEYBOARD_MODIFIER_LEFTGUI + KEYBOARD_MODIFIER_LEFTSHIFT; 
    blehid.keyboardReport(modifier2, undo);
   }
   else
   {
    modifier2 |= KEYBOARD_MODIFIER_LEFTCTRL;
    blehid.keyboardReport(modifier2, redo);
   }
   
   anyKeyPressed = true;
   keyPressedPreviously = true;
  }

  if ( 0 == digitalRead(testPin3) )
  {
   if (num == 1)
   {
   modifier2 |= KEYBOARD_MODIFIER_LEFTALT;
   blehid.keyboardReport(modifier2, alt); 
   }
   else
   {
   modifier2 |= KEYBOARD_MODIFIER_LEFTALT;
   blehid.keyboardReport(0, alt);
   }
   anyKeyPressed = true;
   keyPressedPreviously = true;
  }

  if ( 0 == digitalRead(testPin4) )
  {
   if (num == 1)
   {
   modifier2 |= KEYBOARD_MODIFIER_LEFTGUI;
   blehid.keyboardReport(modifier2, HID_KEY_0);  
   }
   else
   {
   blehid.keyboardReport(0, HID_KEY_TAB);
   }
   anyKeyPressed = true;
   keyPressedPreviously = true;
  }

  if ( 0 == digitalRead(testPin5) )
  {
   if (num == 1)
   {
   blehid.keyboardReport(0, HID_KEY_L);  
   }
   else
   {
   blehid.keyboardReport(0, HID_KEY_CONTROL_LEFT);
   }
   anyKeyPressed = true;
   keyPressedPreviously = true;
  }

  if ( 0 == digitalRead(testPin6) )
  {
   if (num == 1)
   {
   blehid.keyboardReport(0, HID_KEY_SPACE);  
   }
   else
   {
   blehid.keyboardReport(0, HID_KEY_SHIFT_LEFT);
   }
   anyKeyPressed = true;
   keyPressedPreviously = true;
  }

  if ( 0 == digitalRead(testPin7) )
  {
   if (num == 1)
   {
   blehid.keyboardReport(0, HID_KEY_V);  
   }
   else
   {
   blehid.keyboardReport(0, HID_KEY_KEYPAD_ENTER);
   }
   anyKeyPressed = true;
   keyPressedPreviously = true;
  }

  if ( 0 == digitalRead(testPin8) )
  {
   if (num == 1)
   {
   blehid.keyboardReport(0, HID_KEY_S);  
   }
   else
   {
   blehid.keyboardReport(0, HID_KEY_ESCAPE);
   }
   anyKeyPressed = true;
   keyPressedPreviously = true;
  }

  if ( 0 == digitalRead(testPin9) )
  {
   if (num == 1)
   {
   blehid.keyboardReport(0, HID_KEY_B);  
   }
   else
   {
   blehid.keyboardReport(0, HID_KEY_V);
   }
   anyKeyPressed = true;
   keyPressedPreviously = true;
  }


  // scan normal key and send report
  for(uint8_t i=0; i < pincount; i++)
  {
    if ( 0 == digitalRead(pins[i]) )
    {
      // if pin is active (low), add its hid code to key report
      keycode[count++] = hidcode[i];

      // 6 is max keycode per report
      if ( count == 6)
      {
        blehid.keyboardReport(modifier, keycode);

        // reset report
        count = 0;
        memset(keycode, 0, 6);
      }

      // used later
      anyKeyPressed = true;
      keyPressedPreviously = true;
    }    
  }

  // Send any remaining keys (not accumulated up to 6)
  if ( count )
  {
    blehid.keyboardReport(modifier, keycode);
  }

  // Send All-zero report to indicate there is no keys pressed
  // Most of the time, it is, though we don't need to send zero report
  // every loop(), only a key is pressed in previous loop() 
  if ( !anyKeyPressed && keyPressedPreviously )
  {
    keyPressedPreviously = false;
    blehid.keyRelease();
  }  
  
  // Poll interval
  delay(10);
}

/**
 * Callback invoked when received Set LED from central.
 * Must be set previously with setKeyboardLedCallback()
 *
 * The LED bit map is as follows: (also defined by KEYBOARD_LED_* )
 *    Kana (4) | Compose (3) | ScrollLock (2) | CapsLock (1) | Numlock (0)
 */
void set_keyboard_led(uint8_t led_bitmap)
{
  // light up Red Led if any bits is set
  if ( led_bitmap )
  {
    ledOn( LED_RED );
  }
  else
  {
    ledOff( LED_RED );
  }
}
